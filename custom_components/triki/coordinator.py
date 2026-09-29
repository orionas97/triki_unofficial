"""Data update coordinator for a single Triki controller.

This is a *push* coordinator: it does not poll on a timer. Instead it keeps
a persistent BLE connection open and calls ``async_set_updated_data`` every
time a BLE notification arrives (throttled for the high-rate motion data,
immediate for the button state). This is the pattern Home Assistant's own
developer docs describe for push-based APIs.
"""
from __future__ import annotations

import asyncio
import logging
import math
import struct
import time
from dataclasses import dataclass

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ACCEL_LSB_PER_G,
    BATTERY_LEVEL_UUID,
    CMD_PREFIX,
    CMD_SLEEP,
    CMD_SUFFIX,
    CONNECT_TIMEOUT,
    FIRMWARE_REV_UUID,
    LED_CTRL_UUID,
    MIN_PUSH_INTERVAL,
    NOTIFY_HEADER,
    NOTIFY_LEN,
    ORIENTATION_DOMINANCE_RATIO,
    ORIENTATION_MAGNITUDE_TOLERANCE,
    RETRY_COOLDOWN,
    ROTATION_GYRO_THRESHOLD,
    ROTATION_HOLD_SECONDS,
    UART_RX_UUID,
    UART_TX_UUID,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class TrikiData:
    """Latest known state of one Triki controller."""

    available: bool = False
    battery: int | None = None
    firmware: str | None = None
    rssi: int | None = None
    accel_x: int = 0
    accel_y: int = 0
    accel_z: int = 0
    gyro_x: int = 0
    gyro_y: int = 0
    gyro_z: int = 0
    button_pressed: bool = False
    led_on: bool = False

    # Derived (computed here, not part of the raw protocol). Position flags
    # are only ever True while the token is resting still on one face —
    # see ORIENTATION_MAGNITUDE_TOLERANCE / ORIENTATION_DOMINANCE_RATIO.
    pos_up: bool = False  # accelZ ~ +1 g: face up (as tested: rests here most)
    pos_down: bool = False  # accelZ ~ -1 g: face down
    pos_side_left: bool = False  # accelX ~ -1 g: on its side (axis label unverified)
    pos_side_right: bool = False  # accelX ~ +1 g: on its side (axis label unverified)
    pos_horizontal: bool = False  # lying flat on a face: pos_up or pos_down
    pos_vertical: bool = False  # standing on its rim: neither up nor down
    rotating_right: bool = False  # gyroZ > threshold, held briefly after each hit
    rotating_left: bool = False  # gyroZ < -threshold, held briefly after each hit


class TrikiCoordinator(DataUpdateCoordinator[TrikiData]):
    """Owns the BLE connection to one Triki controller."""

    def __init__(self, hass: HomeAssistant, address: str, sample_rate: int) -> None:
        super().__init__(hass, _LOGGER, name=f"Triki {address}", update_interval=None)
        self.address = address
        self.sample_rate = sample_rate
        self.data = TrikiData()

        self._client: BleakClient | None = None
        self._last_push = 0.0
        self._connect_lock = asyncio.Lock()
        self._next_attempt = 0.0
        self._last_rotation_right = float("-inf")
        self._last_rotation_left = float("-inf")
        self._unregister_callbacks: list = []

    @property
    def device_name(self) -> str:
        """Short, human-friendly name derived from the BLE MAC."""
        return f"Triki {self.address.replace(':', '')[-6:]}"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_start(self) -> None:
        """Start tracking the device and connect as soon as it is seen."""
        cancel = bluetooth.async_register_callback(
            self.hass,
            self._async_seen,
            bluetooth.BluetoothCallbackMatcher(address=self.address),
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
        self._unregister_callbacks.append(cancel)

        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is not None:
            _LOGGER.info("Triki %s: seen by Bluetooth, connecting", self.address)
            self._async_schedule_connect(ble_device)
        else:
            _LOGGER.info(
                "Triki %s: not seen by any adapter/proxy yet, waiting for advertisement "
                "(is it still connected to Zappka/phone?)",
                self.address,
            )

    async def async_stop(self) -> None:
        """Stop tracking and disconnect cleanly."""
        for cancel in self._unregister_callbacks:
            cancel()
        self._unregister_callbacks.clear()
        await self._async_disconnect()

    async def async_apply_sample_rate(self, sample_rate: int) -> None:
        """Apply a new sample rate (requires re-sending the start command)."""
        self.sample_rate = sample_rate
        if self._client is not None and self._client.is_connected:
            await self._async_send_start_stream(self._client)

    # ------------------------------------------------------------------
    # Connection handling
    # ------------------------------------------------------------------

    @callback
    def _async_seen(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        if self.data.rssi is None:
            _LOGGER.info(
                "Triki %s: first advertisement received via %s",
                self.address,
                service_info.source,
            )
        self.data.rssi = service_info.rssi
        if self._client is None or not self._client.is_connected:
            self._async_schedule_connect(service_info.device)

    @callback
    def _async_schedule_connect(self, ble_device: BLEDevice) -> None:
        """Connect in the background (never block config entry setup)."""
        if self._connect_lock.locked() or time.monotonic() < self._next_attempt:
            return
        self.hass.async_create_background_task(
            self._async_connect(ble_device), f"triki_connect_{self.address}"
        )

    async def _async_connect(self, ble_device: BLEDevice) -> None:
        async with self._connect_lock:
            if self._client is not None and self._client.is_connected:
                return

            try:
                async with asyncio.timeout(CONNECT_TIMEOUT):
                    client = await establish_connection(
                        BleakClientWithServiceCache,
                        ble_device,
                        self.device_name,
                        disconnected_callback=self._on_disconnect,
                        max_attempts=2,
                    )
            except (BleakError, TimeoutError, EOFError) as err:
                self._next_attempt = time.monotonic() + RETRY_COOLDOWN
                _LOGGER.warning(
                    "Triki %s: connection failed (%r); retrying in %ss. "
                    "Is it still connected to the Zappka app / another device?",
                    self.address,
                    err,
                    RETRY_COOLDOWN,
                )
                return

            self._client = client
            _LOGGER.info("Triki %s: connected", self.address)

            try:
                battery = await client.read_gatt_char(BATTERY_LEVEL_UUID)
                self.data.battery = int(battery[0])
            except (BleakError, IndexError) as err:
                _LOGGER.debug("Triki %s: battery read failed: %s", self.address, err)

            try:
                fw_raw = await client.read_gatt_char(FIRMWARE_REV_UUID)
                self.data.firmware = (
                    fw_raw.decode("utf-8", errors="ignore").strip("\x00").strip()
                )
            except BleakError as err:
                _LOGGER.debug("Triki %s: firmware read failed: %s", self.address, err)

            try:
                await client.start_notify(UART_TX_UUID, self._on_notify)
                await self._async_send_start_stream(client)
            except BleakError as err:
                _LOGGER.warning(
                    "Triki %s: could not start motion stream: %s", self.address, err
                )

            self.data.available = True
            self.async_set_updated_data(self.data)

    async def _async_send_start_stream(self, client: BleakClient) -> None:
        rate_bytes = self.sample_rate.to_bytes(2, byteorder="little")
        start_cmd = CMD_PREFIX + rate_bytes + CMD_SUFFIX
        await client.write_gatt_char(UART_RX_UUID, start_cmd, response=False)

    def _on_disconnect(self, _client: BleakClient) -> None:
        _LOGGER.info("Triki %s: disconnected", self.address)
        self.data.available = False
        self._client = None
        self.hass.loop.call_soon_threadsafe(self.async_set_updated_data, self.data)

    async def _async_disconnect(self) -> None:
        client, self._client = self._client, None
        if client is None:
            return
        try:
            if client.is_connected:
                try:
                    await client.write_gatt_char(LED_CTRL_UUID, b"\x00", response=True)
                except BleakError:
                    pass
                try:
                    await client.write_gatt_char(UART_RX_UUID, CMD_SLEEP, response=False)
                except BleakError:
                    pass
                await client.disconnect()
        except BleakError as err:
            _LOGGER.debug("Triki %s: error during disconnect: %s", self.address, err)

    # ------------------------------------------------------------------
    # Notification parsing
    # ------------------------------------------------------------------

    @callback
    def _on_notify(self, _sender, payload: bytearray) -> None:
        if len(payload) < NOTIFY_LEN or payload[0] != NOTIFY_HEADER:
            return  # not a motion packet (e.g. a 5-byte 0x21 status/ack packet)

        # Byte order confirmed against a real device recording: gyro first
        # (bytes 2-7, ~0 at rest), accel second (bytes 8-13, ~2048 LSB on
        # whichever axis is aligned with gravity). See the note in const.py.
        (
            self.data.gyro_x,
            self.data.gyro_y,
            self.data.gyro_z,
            self.data.accel_x,
            self.data.accel_y,
            self.data.accel_z,
        ) = struct.unpack_from("<hhhhhh", payload, 2)

        button_pressed = payload[15] == 1
        button_changed = button_pressed != self.data.button_pressed
        self.data.button_pressed = button_pressed
        self.data.available = True

        derived_before = self._derived_snapshot()
        self._update_derived()
        derived_changed = derived_before != self._derived_snapshot()

        now = time.monotonic()
        if (
            button_changed
            or derived_changed
            or (now - self._last_push) >= MIN_PUSH_INTERVAL
        ):
            self._last_push = now
            self.async_set_updated_data(self.data)

    def _derived_snapshot(self) -> tuple:
        d = self.data
        return (
            d.pos_up,
            d.pos_down,
            d.pos_side_left,
            d.pos_side_right,
            d.pos_horizontal,
            d.pos_vertical,
            d.rotating_right,
            d.rotating_left,
        )

    def _update_derived(self) -> None:
        """Recompute the position/rotation flags from the latest raw axes."""
        d = self.data

        # --- Rotation (gyro Z / yaw), with a short hold so a single quick
        # spin registers as "on" for long enough for an automation to catch.
        now = time.monotonic()
        if d.gyro_z >= ROTATION_GYRO_THRESHOLD:
            self._last_rotation_right = now
        elif d.gyro_z <= -ROTATION_GYRO_THRESHOLD:
            self._last_rotation_left = now
        d.rotating_right = (now - self._last_rotation_right) <= ROTATION_HOLD_SECONDS
        d.rotating_left = (now - self._last_rotation_left) <= ROTATION_HOLD_SECONDS

        # --- Static position (accel), only claimed while the token is
        # resting close to exactly 1 g total and one axis clearly dominates.
        ax, ay, az = d.accel_x, d.accel_y, d.accel_z
        magnitude = math.sqrt(ax * ax + ay * ay + az * az)
        lo = ACCEL_LSB_PER_G * (1 - ORIENTATION_MAGNITUDE_TOLERANCE)
        hi = ACCEL_LSB_PER_G * (1 + ORIENTATION_MAGNITUDE_TOLERANCE)
        still = lo <= magnitude <= hi

        d.pos_up = d.pos_down = d.pos_side_left = d.pos_side_right = False
        d.pos_horizontal = d.pos_vertical = False

        if still:
            abs_axes = sorted(
                ((abs(ax), "x", ax), (abs(ay), "y", ay), (abs(az), "z", az)),
                reverse=True,
            )
            (top_val, top_axis, top_signed), (second_val, *_), _ = abs_axes
            resolved = second_val == 0 or top_val / second_val >= ORIENTATION_DOMINANCE_RATIO

            if resolved and top_axis == "z":
                d.pos_up = top_signed > 0
                d.pos_down = top_signed < 0
                d.pos_horizontal = True
            elif resolved:
                # dominant axis is X or Y: resting on its rim, not on a face.
                d.pos_vertical = True
                if top_axis == "x":
                    d.pos_side_left = top_signed < 0
                    d.pos_side_right = top_signed > 0
                # a dominant Y axis is "on its side" too, but this build
                # doesn't assign it a separate front/back label (not asked
                # for) — it still correctly counts as pos_vertical.

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def async_set_led(self, on: bool) -> None:
        """Turn the controller's green LED on or off.

        The remote device occasionally answers a write with GATT error 0x0E
        ("Unlikely Error") — seen in practice over a relayed ESPHome proxy
        connection, even though the write is byte-for-byte identical to the
        two reference Python implementations. Retry a couple of times before
        giving up, and surface a clean error instead of a raw traceback.
        """
        if self._client is None or not self._client.is_connected:
            raise HomeAssistantError("Kontroler Triki nie jest teraz połączony")

        payload = b"\x01" if on else b"\x00"
        last_err: BleakError | None = None
        for attempt in range(3):
            try:
                await self._client.write_gatt_char(
                    LED_CTRL_UUID, payload, response=True
                )
                self.data.led_on = on
                self.async_set_updated_data(self.data)
                return
            except BleakError as err:
                last_err = err
                _LOGGER.debug(
                    "Triki %s: LED write attempt %s/3 failed: %s",
                    self.address,
                    attempt + 1,
                    err,
                )
                if attempt < 2:
                    await asyncio.sleep(0.3)

        raise HomeAssistantError(
            f"Nie udało się ustawić diody LED w kontrolerze Triki: {last_err}"
        ) from last_err
