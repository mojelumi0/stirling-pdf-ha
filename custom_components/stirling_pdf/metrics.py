"""Optional, listener-driven monitoring, isolated from base availability."""

from __future__ import annotations

import logging
import math
import re
import sys
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MAX_LENGTH_STATE_STATE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import StirlingPdfApiClient, StirlingPdfApiError

_LOGGER = logging.getLogger(__name__)

# HA validates numeric sensor states as floats and stores at most 255 characters.
# Compare integers directly, without converting huge values to float or text.
_MAX_METRIC_INTEGER = min(int(sys.float_info.max), 10**MAX_LENGTH_STATE_STATE - 1)

ENDPOINTS = {
    "uptime": "/api/v1/info/uptime",
    "post_requests": "/api/v1/info/requests",
    "get_requests": "/api/v1/info/load",
    "jobs": "/api/v1/admin/job/stats",
    "queue": "/api/v1/admin/job/queue/stats",
    "ocr_languages": "/api/v1/ui-data/ocr-pdf",
    "ai_health": "/api/v1/ai/health",
    "ai_status": "/api/v1/ai/status",
    "indexing": "/api/v1/docparse/capabilities",
}


@dataclass(frozen=True)
class Metric:
    """One optional sensor; all are disabled in the entity registry initially."""

    key: str
    group: str
    field: str = ""
    kind: str = "number"
    unit: str | None = None


METRICS = (
    Metric("uptime", "uptime", kind="duration", unit="s"),
    Metric("post_requests", "post_requests"),
    Metric("get_requests", "get_requests"),
    Metric("total_jobs", "jobs", "totalJobs"),
    Metric("active_jobs", "jobs", "activeJobs"),
    Metric("completed_jobs", "jobs", "completedJobs"),
    Metric("failed_jobs", "jobs", "failedJobs"),
    Metric("successful_jobs", "jobs", "successfulJobs"),
    Metric("file_result_jobs", "jobs", "fileResultJobs"),
    Metric("average_processing_time", "jobs", "averageProcessingTimeMs", unit="ms"),
    Metric("oldest_active_job", "jobs", "oldestActiveJobTime", kind="text"),
    Metric("newest_active_job", "jobs", "newestActiveJobTime", kind="text"),
    Metric("queued_jobs", "queue", "queuedJobs"),
    Metric("queue_capacity", "queue", "queueCapacity"),
    Metric("total_queued_jobs", "queue", "totalQueuedJobs"),
    Metric("rejected_jobs", "queue", "rejectedJobs"),
    Metric("resource_status", "queue", "resourceStatus", kind="text"),
    Metric("ocr_languages", "ocr_languages", "languages", kind="languages"),
    Metric("ai_health", "ai_health", "status", kind="text"),
    Metric("ai_smart_model", "ai_status", "smartModel", kind="text"),
    Metric("ai_fast_model", "ai_status", "fastModel", kind="text"),
    Metric("ai_latency", "ai_status", "latencyMs", unit="ms"),
)

BOOLEAN_METRICS = (
    Metric("ai_enabled", "ai_status", "enabled", kind="boolean"),
    Metric("ai_reachable", "ai_status", "reachable", kind="boolean"),
    Metric("ai_authenticated", "ai_status", "authenticated", kind="boolean"),
    Metric("document_parsing_enabled", "indexing", "enabled", kind="boolean"),
    Metric("document_parsing_reachable", "indexing", "engineReachable", kind="boolean"),
    Metric("indexing_ready", "indexing", "indexingConfigured", kind="boolean"),
)


def languages(value: Any) -> list[str]:
    """Accept bounded language codes only, never arbitrary response objects."""
    if not isinstance(value, list):
        return []
    return sorted(
        {
            item
            for item in value[:256]
            if isinstance(item, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,32}", item)
        }
    )


def metric_value(data: Any, description: Metric) -> int | float | str | bool | None:
    """Reject missing/invalid data rather than displaying invented zero values."""
    value = data.get(description.field) if isinstance(data, dict) else data
    if description.kind == "languages":
        return len(languages(value)) if isinstance(value, list) else None
    if description.kind == "text":
        return (
            value
            if isinstance(value, str) and 0 < len(value) <= MAX_LENGTH_STATE_STATE
            else None
        )
    if description.kind == "boolean":
        return value if isinstance(value, bool) else None
    if description.kind == "duration":
        match = (
            re.fullmatch(r"(\d+)d (\d+)h (\d+)m (\d+)s", value)
            if isinstance(value, str) and len(value) <= MAX_LENGTH_STATE_STATE
            else None
        )
        if not match:
            return None
        days, hours, minutes, seconds = map(int, match.groups())
        value = days * 86400 + hours * 3600 + minutes * 60 + seconds
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, int):
        return value if 0 <= value <= _MAX_METRIC_INTEGER else None
    return value if math.isfinite(value) and value >= 0 else None


class StirlingPdfMetricsCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch each endpoint once, only while an enabled entity subscribes to it."""

    def __init__(
        self, hass: HomeAssistant, client: StirlingPdfApiClient, entry: ConfigEntry
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"stirling_pdf_metrics_{entry.entry_id}",
            config_entry=entry,
            update_interval=timedelta(seconds=60),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        result = {}
        for group in sorted(set(self.async_contexts()) & ENDPOINTS.keys()):
            try:
                result[group] = await self.client.async_get_optional_data(
                    ENDPOINTS[group]
                )
            except StirlingPdfApiError:
                # Monitoring errors do not trigger base reauth or leak server bodies.
                result[group] = None
        return result
