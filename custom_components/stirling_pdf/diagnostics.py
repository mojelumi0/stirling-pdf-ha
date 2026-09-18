"""Diagnostics support for Stirling PDF."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant

from .coordinator import StirlingPdfCoordinator

_TO_REDACT = {
    CONF_API_KEY,
    CONF_URL,
    "apiKey",
    "authorization",
    "password",
    "token",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry[StirlingPdfCoordinator],
) -> dict[str, Any]:
    """Return sanitized diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "config_entry": async_redact_data(entry.data, _TO_REDACT),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "status": async_redact_data(coordinator.data or {}, _TO_REDACT),
            "jobs_processed": coordinator.jobs_processed,
            "last_operation": coordinator.last_operation,
            "last_operation_time": (
                coordinator.last_operation_time.isoformat()
                if coordinator.last_operation_time is not None
                else None
            ),
        },
    }
