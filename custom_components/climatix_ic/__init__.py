"""The Climatix IC integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .client import ClimatixClient
from .const import CONF_PLANT_ID, CONF_SCAN_INTERVAL, CONF_TOTP_SECRET, DEFAULT_SCAN_INTERVAL
from .coordinator import ClimatixCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

type ClimatixConfigEntry = ConfigEntry[ClimatixCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ClimatixConfigEntry) -> bool:
    """Set up Climatix IC from a config entry."""
    client = ClimatixClient(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_TOTP_SECRET],
        entry.data[CONF_PLANT_ID],
    )
    scan = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = ClimatixCoordinator(hass, client, scan)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_reload_on_options))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ClimatixConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _reload_on_options(hass: HomeAssistant, entry: ClimatixConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
