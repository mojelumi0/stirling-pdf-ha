"""Tests for defensive statistics loading and coordinator error mapping."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stirling_pdf.api import (
    StirlingPdfApiClient,
    StirlingPdfAuthError,
    StirlingPdfConnectionError,
)
from custom_components.stirling_pdf.const import DEFAULT_SCAN_INTERVAL
from custom_components.stirling_pdf.coordinator import StirlingPdfCoordinator


@pytest.fixture
def coordinator(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> StirlingPdfCoordinator:
    """Construct a coordinator without network calls or entity setup."""
    return StirlingPdfCoordinator(
        hass,
        MagicMock(spec=StirlingPdfApiClient),
        DEFAULT_SCAN_INTERVAL,
        mock_config_entry,
    )


@pytest.mark.parametrize(
    ("stored", "jobs", "operation", "timestamp"),
    [
        (None, 0, None, None),
        ([], 0, None, None),
        ({}, 0, None, None),
        ({"jobs_processed": True}, 0, None, None),
        ({"jobs_processed": -1}, 0, None, None),
        ({"jobs_processed": "12"}, 0, None, None),
        ({"jobs_processed": 12, "last_operation": "unknown"}, 12, None, None),
        ({"jobs_processed": 12, "last_operation": "ocr"}, 12, "ocr", None),
        ({"last_operation": "ocr", "last_operation_time": 42}, 0, "ocr", None),
        (
            {"last_operation": "ocr", "last_operation_time": "invalid"},
            0,
            "ocr",
            None,
        ),
        (
            {"last_operation": "ocr", "last_operation_time": "2026-10-20T12:00:00"},
            0,
            "ocr",
            None,
        ),
        (
            {
                "jobs_processed": 12,
                "last_operation": "compress",
                "last_operation_time": "2026-10-20T14:00:00+02:00",
            },
            12,
            "compress",
            datetime(2026, 10, 20, 12, tzinfo=UTC),
        ),
    ],
)
async def test_statistics_restore_valid_fields_without_accepting_corruption(
    coordinator: StirlingPdfCoordinator,
    stored: Any,
    jobs: int,
    operation: str | None,
    timestamp: datetime | None,
) -> None:
    """Ignore invalid stored values and normalize aware timestamps to UTC."""
    with patch.object(coordinator._store, "async_load", AsyncMock(return_value=stored)):
        await coordinator.async_load_statistics()
    assert coordinator.jobs_processed == jobs
    assert coordinator.last_operation == operation
    assert coordinator.last_operation_time == timestamp


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (StirlingPdfAuthError("rejected"), ConfigEntryAuthFailed),
        (StirlingPdfConnectionError("offline"), UpdateFailed),
    ],
)
async def test_update_errors_are_mapped_and_can_recover(
    coordinator: StirlingPdfCoordinator,
    error: Exception,
    expected: type[Exception],
) -> None:
    """Preserve local statistics across an API failure and successful retry."""
    coordinator.jobs_processed = 12
    status = {"status": "UP", "version": "3.2.0"}
    coordinator.client.async_validate_connection = AsyncMock(
        side_effect=[error, status]
    )
    with pytest.raises(expected):
        await coordinator._async_update_data()
    assert await coordinator._async_update_data() == status
    assert coordinator.jobs_processed == 12


async def test_empty_statistics_can_be_saved(
    coordinator: StirlingPdfCoordinator,
) -> None:
    """A fresh instance stores JSON nulls rather than a fabricated operation."""
    with patch.object(coordinator._store, "async_save", AsyncMock()) as save:
        await coordinator.async_save_statistics()
    save.assert_awaited_once_with(
        {"jobs_processed": 0, "last_operation": None, "last_operation_time": None}
    )
