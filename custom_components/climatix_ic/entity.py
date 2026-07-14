"""Shared entity base for Climatix IC."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_PLANT_ID, DOMAIN, MANUFACTURER
from .coordinator import ClimatixCoordinator


class ClimatixEntity(CoordinatorEntity[ClimatixCoordinator]):
    """Common wiring: one HA entity per Climatix datapoint."""

    # False: friendly name is the caption alone, not "<plant> <caption>" - a single hub is
    # the common case, so the plant prefix is just noise. entity_id stays namespaced (below).
    _attr_has_entity_name = False

    def __init__(
        self, coordinator: ClimatixCoordinator, entry: ConfigEntry, desc: dict, platform: str
    ) -> None:
        super().__init__(coordinator)
        self._pid = desc["pid"]
        self._attr_name = desc["name"]  # Climatix caption -> friendly name only
        self._attr_unique_id = f"{entry.entry_id}_{desc['pid']}"
        # The entity_id must NOT start with the (arbitrary, mutable) plant name, or a plant
        # called e.g. "bthome" would collide with another integration. Namespace it with our
        # domain, a short plant discriminator (plants can share a name), and the datapoint id:
        #   sensor.climatix_ic_ece2026b_boiler_temp_setpoint_1311
        plant_short = entry.data[CONF_PLANT_ID].split("-", 1)[0]
        object_id = f"{DOMAIN}_{plant_short}_{desc['slug']}_{desc['pid']}"
        self.entity_id = async_generate_entity_id(f"{platform}.{{}}", object_id, hass=coordinator.hass)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_PLANT_ID])},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model="Climatix IC",
        )

    @property
    def _value(self):
        return self.coordinator.data.get(self._pid)
