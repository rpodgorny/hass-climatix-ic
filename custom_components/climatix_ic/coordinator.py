"""Data update coordinator for Climatix IC."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import AuthError, ClimatixClient, ClimatixError
from .const import DOMAIN, LOGGER


class ClimatixCoordinator(DataUpdateCoordinator[dict]):
    """Logs in once, discovers datapoints once, then re-reads values every interval."""

    def __init__(self, hass: HomeAssistant, client: ClimatixClient, scan_interval: int) -> None:
        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=timedelta(seconds=scan_interval))
        self.client = client
        self.descriptors: list[dict] | None = None

    async def _async_update_data(self) -> dict:
        def work() -> dict:
            if self.client.s is None:
                self.client.login()
            if self.descriptors is None:
                self.descriptors = self.client.discover()
            return self.client.read_values(self.descriptors)

        try:
            return await self.hass.async_add_executor_job(work)
        except AuthError as e:
            raise ConfigEntryAuthFailed(str(e)) from e
        except ClimatixError as e:
            raise UpdateFailed(str(e)) from e
        except Exception as e:  # network etc.
            raise UpdateFailed(str(e)) from e
