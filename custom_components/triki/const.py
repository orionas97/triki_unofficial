"""Constants for the Triki (Żabka) integration.

The BLE protocol constants below are NOT invented — they were cross-checked
against three independent, public reverse-engineering projects that all
agree on the same UUIDs and byte layout:

  - https://github.com/Wojtekb30/unofficial-triki-api-py
  - https://github.com/woofter-wolf/triki-library-python
  - https://github.com/Flopsstuff/triki (docs/guide/ble-protocol.md)

Where the three sources disagreed slightly (e.g. exact packet length used
in parsing), the more complete/newer source was used and is noted inline.
"""
from __future__ import annotations

DOMAIN = "triki"

# --- GATT UUIDs -------------------------------------------------------
# Nordic UART Service (NUS) plus one custom characteristic for the LED.
UART_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
UART_RX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # write: host -> device
UART_TX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # notify: device -> host
LED_CTRL_UUID = "6e400004-b5a3-f393-e0a9-e50e24dcca9e"  # read/write, 1 byte, green LED

# Standard Bluetooth SIG characteristics (Battery Service / Device Information)
BATTERY_LEVEL_UUID = "00002a19-0000-1000-8000-00805f9b34fb"
FIRMWARE_REV_UUID = "00002a26-0000-1000-8000-00805f9b34fb"

# --- Commands written to UART_RX_UUID ----------------------------------
# 8-byte "start IMU stream" command.
#   byte 0-2 : 20 10 00        (fixed opcode, not decoded further)
#   byte 3-4 : D0 07           (fixed, not decoded further)
#   byte 5-6 : sample rate in Hz, little-endian uint16 (this part IS decoded
#              and documented: 26/52/104/208/416 are the LSM6DSL steps the
#              firmware accepts; 12.5 Hz is rejected by the device)
#   byte 7   : 03              (fixed)
CMD_PREFIX = bytes((0x20, 0x10, 0x00, 0xD0, 0x07))
CMD_SUFFIX = bytes((0x03,))

# Sleep / stop-stream command, sent before disconnecting to save battery.
CMD_SLEEP = bytes((0x20, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00))

SAMPLE_RATES: list[int] = [26, 52, 104, 208, 416]
DEFAULT_SAMPLE_RATE = 104

CONF_SAMPLE_RATE = "sample_rate"

# --- Notification packets on UART_TX_UUID ------------------------------
# 16-byte motion packet:
#   byte 0    : 0x22 header (motion data)
#   byte 1    : reserved / always 0x00
#   byte 2-3  : gyro X    (int16, little-endian)
#   byte 4-5  : gyro Y
#   byte 6-7  : gyro Z
#   byte 8-9  : accel X
#   byte 10-11: accel Y
#   byte 12-13: accel Z
#   byte 14   : reserved
#   byte 15   : button pressed flag (1 = pressed, 0 = released)
#
# CORRECTED 2026-09-28: an earlier version of this file had accel/gyro
# swapped (accel first, gyro second), following unofficial-triki-api-py's
# naming. Real recorded data from a live device proved that wrong: the
# *second* group of three axes holds a constant ≈2048 LSB (=1 g, matching
# the documented ±16 g / 2048-LSB-per-g scale) on whichever axis is
# aligned with gravity while the token is still — that is the
# accelerometer. The *first* group sits near 0 at rest and only moves
# during rotation — that is the gyroscope. This byte order (gyro then
# accel) matches Flopsstuff/triki's docs/guide/imu-streaming.md, which
# documents the same layout and scale factors from an independent test.
#
# Scales (from Flopsstuff/triki docs/guide/imu-streaming.md):
#   gyro raw / GYRO_LSB_PER_DPS  -> deg/s   (LSM6DSL ±2000 dps)
#   accel raw / ACCEL_LSB_PER_G  -> g       (LSM6DSL ±16 g)
GYRO_LSB_PER_DPS = 14.286
ACCEL_LSB_PER_G = 2048.0

# A separate 5-byte packet starting with 0x21 is a status/ack packet
# (e.g. on wake/sleep) and carries no motion data — it is ignored here.
NOTIFY_HEADER = 0x22
NOTIFY_LEN = 16

# --- Orientation / gesture detection (derived, not part of the raw
# protocol — computed here from the accel/gyro values above) -----------
# A face is reported as "up"/"down"/"on its side" only while the token is
# essentially still (total accel magnitude within this fraction of 1 g);
# during active motion none of the position sensors claim a face.
ORIENTATION_MAGNITUDE_TOLERANCE = 0.35  # +/- 35% of 1 g
# The dominant axis must exceed the other two by at least this multiple
# to call a face "up" confidently (avoids flip-flopping near diagonals).
ORIENTATION_DOMINANCE_RATIO = 1.8
# Gyro Z threshold (raw LSB) and minimum hold time for the rotation
# left/right binary sensors, empirically generous vs. the ~(-5,-8,-10)
# idle noise floor seen in real recordings.
ROTATION_GYRO_THRESHOLD = 400
ROTATION_HOLD_SECONDS = 0.4

# Throttle: continuous accel/gyro values are pushed to HA entities at most
# this often, so a 26-416 Hz BLE stream doesn't flood the state machine /
# recorder database. A button-state change always bypasses the throttle.
MIN_PUSH_INTERVAL = 0.5  # seconds

# Connection handling (seconds)
CONNECT_TIMEOUT = 40
RETRY_COOLDOWN = 30

PLATFORMS = ["sensor", "binary_sensor", "switch"]

MANUFACTURER = "Żabka / HopX (unofficial)"
MODEL = "Triki"
