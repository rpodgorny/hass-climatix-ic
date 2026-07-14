"""Shared entity base for Climatix IC."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_PLANT_ID, DOMAIN, MANUFACTURER
from .coordinator import ClimatixCoordinator


class ClimatixEntity(CoordinatorEntity[ClimatixCoordinator]):
    """Common wiring: one HA entity per Climatix datapoint."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ClimatixCoordinator, entry: ConfigEntry, desc: dict) -> None:
        super().__init__(coordinator)
        self._pid = desc["pid"]
        self._attr_name = desc["name"]  # the Climatix caption
        self._attr_unique_id = f"{entry.entry_id}_{desc['pid']}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_PLANT_ID])},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model="Climatix IC",
        )

    @property
    def _value(self):
        return self.coordinator.data.get(self._pid)
