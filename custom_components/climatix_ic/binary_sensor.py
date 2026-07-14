"""Binary sensor platform for Climatix IC (pumps and other On/Off datapoints)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ClimatixConfigEntry
from .entity import ClimatixEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ClimatixConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        ClimatixBinarySensor(coordinator, entry, d)
        for d in coordinator.descriptors
        if d["component"] == "binary_sensor"
    )


class ClimatixBinarySensor(ClimatixEntity, BinarySensorEntity):
    """An On/Off datapoint (pump state, etc.)."""

    def __init__(self, coordinator, entry, desc) -> None:
        super().__init__(coordinator, entry, desc, "binary_sensor")

    @property
    def is_on(self):
        v = self._value
        return None if v is None else v == "On"
