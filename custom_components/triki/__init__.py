"""The Triki (Żabka) integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_SAMPLE_RATE, DEFAULT_SAMPLE_RATE, DOMAIN
from .coordinator import TrikiCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Triki from a config entry."""
    address = entry.data[CONF_ADDRESS]
    sample_rate = entry.options.get(CONF_SAMPLE_RATE, DEFAULT_SAMPLE_RATE)

    coordinator = TrikiCoordinator(hass, address, sample_rate)
    await coordinator.async_start()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: TrikiCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_stop()
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update (e.g. a changed sample rate)."""
    coordinator: TrikiCoordinator = hass.data[DOMAIN][entry.entry_id]
    new_rate = entry.options.get(CONF_SAMPLE_RATE, DEFAULT_SAMPLE_RATE)
    await coordinator.async_apply_sample_rate(new_rate)
