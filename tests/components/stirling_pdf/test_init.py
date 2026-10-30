"""Tests for setup, entities, and unload behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stirling_pdf import async_unload_entry
from custom_components.stirling_pdf import binary_sensor as binary_sensor_platform
from custom_components.stirling_pdf import sensor as sensor_platform
from custom_components.stirling_pdf.api import StirlingPdfAuthError
from custom_components.stirling_pdf.const import DOMAIN


def _entity_id(
    hass: HomeAssistant,
    platform: str,
    entry: MockConfigEntry,
    suffix: str,
) -> str:
    """Return an entity ID from its stable unique ID."""
    entity_id = er.async_get(hass).async_get_entity_id(
        platform,
        DOMAIN,
        f"{entry.entry_id}_{suffix}",
    )
    assert entity_id is not None
    return entity_id


def _state(hass: HomeAssistant, entity_id: str):
    """Return a state while keeping missing entities an explicit test failure."""
    state = hass.states.get(entity_id)
    assert state is not None
    return state


async def test_setup_creates_expected_entities_and_device(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Test the initial coordinator refresh and entity states."""
    assert loaded_entry.state is ConfigEntryState.LOADED

    reachable = _entity_id(hass, "binary_sensor", loaded_entry, "reachable")
    version = _entity_id(hass, "sensor", loaded_entry, "version")
    jobs = _entity_id(hass, "sensor", loaded_entry, "jobs_processed")
    last_operation = _entity_id(hass, "sensor", loaded_entry, "last_operation")

    assert _state(hass, reachable).state == "on"
    assert _state(hass, version).state == "2.14.3"
    assert _state(hass, jobs).state == "0"
    assert _state(hass, last_operation).state == "unknown"

    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, loaded_entry.entry_id),
        loaded_entry.entry_id,
    )
    assert device is not None
    assert device.manufacturer == "Stirling PDF"
    assert device.configuration_url == "http://pdf.local:8080"


async def test_setup_passes_saved_basic_credentials_to_the_runtime_client(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    enable_custom_integrations: None,
) -> None:
    """Reusing an existing entry must load its optional HTTP credentials."""
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            CONF_USERNAME: "test-user",
            CONF_PASSWORD: "test-password",
        },
    )
    with patch(
        "custom_components.stirling_pdf.api.StirlingPdfApiClient.async_validate_connection",
        new=AsyncMock(return_value={"status": "UP", "version": "3.2.0"}),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    headers = mock_config_entry.runtime_data.client._headers()
    assert headers["X-API-KEY"] == "stored-secret"
    assert headers["Authorization"] == "Basic dGVzdC11c2VyOnRlc3QtcGFzc3dvcmQ="


async def test_local_statistics_remain_available_during_api_failure(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Test connectivity and local sensors after a failed coordinator update."""
    coordinator = loaded_entry.runtime_data
    coordinator.record_operation("merge")
    coordinator.async_set_update_error(UpdateFailed("offline"))
    await hass.async_block_till_done()

    reachable = _entity_id(hass, "binary_sensor", loaded_entry, "reachable")
    version = _entity_id(hass, "sensor", loaded_entry, "version")
    jobs = _entity_id(hass, "sensor", loaded_entry, "jobs_processed")
    last_operation = _entity_id(hass, "sensor", loaded_entry, "last_operation")

    assert _state(hass, reachable).state == "off"
    assert _state(hass, version).state == "unavailable"
    assert _state(hass, jobs).state == "1"
    assert _state(hass, last_operation).state == "merge"
    assert "last_run" in _state(hass, last_operation).attributes


@pytest.mark.parametrize("operation", ["ocr", "extract_pages"])
async def test_local_statistics_persist_across_reload(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    operation: str,
) -> None:
    """Test successful-operation statistics survive an integration reload."""
    coordinator = loaded_entry.runtime_data
    coordinator.record_operation(operation)
    recorded_time = coordinator.last_operation_time

    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "custom_components.stirling_pdf.api.StirlingPdfApiClient.async_validate_connection",
        new=AsyncMock(return_value={"status": "UP", "version": "2.14.3"}),
    ):
        assert await hass.config_entries.async_setup(loaded_entry.entry_id)
        await hass.async_block_till_done()

    restored = loaded_entry.runtime_data
    assert restored.jobs_processed == 1
    assert restored.last_operation == operation
    assert restored.last_operation_time == recorded_time


async def test_unload_entry(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Test unloading both entity platforms."""
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()

    assert loaded_entry.state is ConfigEntryState.NOT_LOADED


async def test_rejected_credentials_during_setup_start_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    enable_custom_integrations: None,
) -> None:
    """Start reauthentication when the protected access check fails."""
    with patch(
        "custom_components.stirling_pdf.api.StirlingPdfApiClient.async_validate_connection",
        new=AsyncMock(side_effect=StirlingPdfAuthError("Missing key")),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    reauth_flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["handler"] == DOMAIN and flow["context"]["source"] == SOURCE_REAUTH
    ]
    assert len(reauth_flows) == 1


async def test_remove_entry_deletes_persisted_statistics(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Test removing the config entry also removes its local statistics."""
    coordinator = loaded_entry.runtime_data
    coordinator.record_operation("split")
    await coordinator.async_save_statistics()

    assert await coordinator._store.async_load() is not None

    await hass.config_entries.async_remove(loaded_entry.entry_id)
    await hass.async_block_till_done()

    assert await coordinator._store.async_load() is None


def test_coordinator_platforms_declare_parallel_updates() -> None:
    """Read-only coordinator entities do not need a per-entity update semaphore."""
    assert sensor_platform.PARALLEL_UPDATES == 0
    assert binary_sensor_platform.PARALLEL_UPDATES == 0


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ({}, "unknown"),
        ({"appVersion": "3.2.0"}, "3.2.0"),
        ({"status": "UP"}, "unknown"),
    ],
)
async def test_version_sensor_handles_legacy_or_missing_version(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    status: dict[str, str],
    expected: str,
) -> None:
    """Do not invent a version if status omits it; support the legacy key."""
    loaded_entry.runtime_data.async_set_updated_data(status)
    await hass.async_block_till_done()
    assert (
        _state(hass, _entity_id(hass, "sensor", loaded_entry, "version")).state
        == expected
    )


async def test_failed_platform_unload_does_not_save_or_report_success(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Respect a platform that cannot unload instead of pretending removal worked."""
    with (
        patch.object(
            hass.config_entries, "async_unload_platforms", AsyncMock(return_value=False)
        ),
        patch.object(
            loaded_entry.runtime_data, "async_save_statistics", AsyncMock()
        ) as save,
    ):
        assert not await async_unload_entry(hass, loaded_entry)
    save.assert_not_awaited()
