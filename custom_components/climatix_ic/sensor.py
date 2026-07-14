"""Sensor platform for Climatix IC (temperatures, percentages, status text)."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ClimatixConfigEntry
from .entity import ClimatixEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ClimatixConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        ClimatixSensor(coordinator, entry, d)
        for d in coordinator.descriptors
        if d["component"] == "sensor"
    )


class ClimatixSensor(ClimatixEntity, SensorEntity):
    """A numeric measurement or a status-text datapoint."""

    def __init__(self, coordinator, entry, desc) -> None:
        super().__init__(coordinator, entry, desc)
        self._numeric = desc.get("numeric", False)
        if self._numeric:
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_native_unit_of_measurement = desc.get("unit")
            if desc.get("temperature"):
                self._attr_device_class = SensorDeviceClass.TEMPERATURE

    @property
    def native_value(self):
        v = self._value
        if v is None:
            return None
        if not self._numeric:
            return v
        try:
            return float(v)
        except ValueError:
            return None
