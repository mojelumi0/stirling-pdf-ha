"""Tests for setup, entities, and unload behavior."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

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


async def test_unload_entry(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Test unloading both entity platforms."""
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()

    assert loaded_entry.state is ConfigEntryState.NOT_LOADED
