"""Config flow for the Triki (Żabka) integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_SAMPLE_RATE, DEFAULT_SAMPLE_RATE, DOMAIN, SAMPLE_RATES


def _looks_like_triki(service_info: BluetoothServiceInfoBleak) -> bool:
    """Match both 'Triki <serial>' and 'TRIKI <serial>' advertised names."""
    name = (service_info.name or "").lower()
    return "triki" in name


class TrikiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Triki."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle a flow initiated by Bluetooth discovery."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        if not _looks_like_triki(discovery_info):
            return self.async_abort(reason="not_supported")

        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or discovery_info.address
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery from Bluetooth."""
        assert self._discovery_info is not None

        if user_input is not None:
            return self.async_create_entry(
                title=self._discovery_info.name or self._discovery_info.address,
                data={CONF_ADDRESS: self._discovery_info.address},
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": self._discovery_info.name or self._discovery_info.address
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow started manually from Settings -> Add integration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._discovered_devices[address],
                data={CONF_ADDRESS: address},
            )

        current_addresses = self._async_current_ids()
        for discovery_info in async_discovered_service_info(self.hass):
            if discovery_info.address in current_addresses:
                continue
            if not _looks_like_triki(discovery_info):
                continue
            self._discovered_devices[discovery_info.address] = (
                discovery_info.name or discovery_info.address
            )

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(self._discovered_devices)}
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> TrikiOptionsFlow:
        """Get the options flow for this handler."""
        return TrikiOptionsFlow()


class TrikiOptionsFlow(config_entries.OptionsFlow):
    """Options flow: change the IMU sample rate."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(CONF_SAMPLE_RATE, DEFAULT_SAMPLE_RATE)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SAMPLE_RATE, default=current): vol.In(
                        SAMPLE_RATES
                    )
                }
            ),
        )
