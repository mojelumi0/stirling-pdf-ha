"""Data update coordinator for Stirling PDF."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import StirlingPdfApiClient, StirlingPdfApiError, StirlingPdfAuthError
from .const import DOMAIN, SERVICES

_LOGGER = logging.getLogger(__name__)

_STORAGE_VERSION = 1
_STORAGE_SAVE_DELAY = 1.0


def _statistics_store(
    hass: HomeAssistant,
    entry_id: str,
) -> Store[dict[str, Any]]:
    """Return the operation-statistics store for a config entry."""
    return Store(hass, _STORAGE_VERSION, f"{DOMAIN}.{entry_id}.statistics")


async def async_remove_statistics(hass: HomeAssistant, entry_id: str) -> None:
    """Remove persisted statistics after deleting a config entry."""
    await _statistics_store(hass, entry_id).async_remove()


class StirlingPdfCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll status and store counters for operations started by Home Assistant."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: StirlingPdfApiClient,
        update_interval: timedelta,
        entry_id: str,
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
        self._store = _statistics_store(hass, entry_id)

    async def async_load_statistics(self) -> None:
        """Restore locally recorded operation statistics."""
        stored = await self._store.async_load()
        if not isinstance(stored, dict):
            return

        jobs_processed = stored.get("jobs_processed")
        if (
            isinstance(jobs_processed, int)
            and not isinstance(jobs_processed, bool)
            and jobs_processed >= 0
        ):
            self.jobs_processed = jobs_processed

        last_operation = stored.get("last_operation")
        if last_operation not in SERVICES:
            return
        self.last_operation = last_operation

        last_operation_time = stored.get("last_operation_time")
        if not isinstance(last_operation_time, str):
            return
        try:
            parsed_time = datetime.fromisoformat(last_operation_time)
        except ValueError:
            return
        if parsed_time.tzinfo is not None:
            self.last_operation_time = parsed_time.astimezone(UTC)

    def _statistics_data(self) -> dict[str, Any]:
        """Return JSON-serializable operation statistics."""
        return {
            "jobs_processed": self.jobs_processed,
            "last_operation": self.last_operation,
            "last_operation_time": (
                self.last_operation_time.isoformat()
                if self.last_operation_time is not None
                else None
            ),
        }

    async def async_save_statistics(self) -> None:
        """Immediately persist operation statistics."""
        await self._store.async_save(self._statistics_data())

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
        self._store.async_delay_save(self._statistics_data, _STORAGE_SAVE_DELAY)
        self.async_update_listeners()
