"""Data update coordinator for Stirling PDF."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import StirlingPdfApiClient, StirlingPdfApiError, StirlingPdfAuthError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class StirlingPdfCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll status and store counters for operations started by Home Assistant."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: StirlingPdfApiClient,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.client = client
        self.jobs_processed = 0
        self.last_operation: str | None = None
        self.last_operation_time: datetime | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch current server status."""
        try:
            return await self.client.async_get_status()
        except StirlingPdfAuthError as err:
            raise ConfigEntryAuthFailed from err
        except StirlingPdfApiError as err:
            raise UpdateFailed(f"Communication failed: {err}") from err

    def record_operation(self, name: str) -> None:
        """Record one successful service action and notify entities."""
        self.jobs_processed += 1
        self.last_operation = name
        self.last_operation_time = datetime.now(UTC)
        self.async_update_listeners()
