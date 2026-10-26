"""Tests for Stirling PDF diagnostics."""

from __future__ import annotations

import json

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stirling_pdf.diagnostics import (
    async_get_config_entry_diagnostics,
)


@pytest.mark.parametrize(
    "authentication_check_supported",
    [True, False, None],
    ids=["supported", "unsupported", "not-checked"],
)
async def test_diagnostics_are_useful_and_redacted(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    authentication_check_supported: bool | None,
) -> None:
    """Test diagnostics include runtime details without private configuration."""
    loaded_entry.runtime_data.record_operation("merge")
    loaded_entry.runtime_data.client.authentication_check_supported = (
        authentication_check_supported
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, loaded_entry)
    serialized = json.dumps(diagnostics)

    assert "stored-secret" not in serialized
    assert "pdf.local" not in serialized
    assert diagnostics["coordinator"]["last_update_success"] is True
    assert (
        diagnostics["coordinator"]["authentication_check_supported"]
        is authentication_check_supported
    )
    assert diagnostics["coordinator"]["status"] == {
        "status": "UP",
        "version": "2.14.3",
    }
    assert diagnostics["coordinator"]["jobs_processed"] == 1
    assert diagnostics["coordinator"]["last_operation"] == "merge"
    assert diagnostics["coordinator"]["last_operation_time"] is not None


async def test_diagnostics_before_the_first_operation(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Represent missing local history and empty server data without fabrication."""
    loaded_entry.runtime_data.async_set_updated_data({})
    diagnostics = await async_get_config_entry_diagnostics(hass, loaded_entry)
    assert diagnostics["coordinator"]["status"] == {}
    assert diagnostics["coordinator"]["jobs_processed"] == 0
    assert diagnostics["coordinator"]["last_operation"] is None
    assert diagnostics["coordinator"]["last_operation_time"] is None
    assert "stored-secret" not in json.dumps(diagnostics)
    assert "pdf.local" not in json.dumps(diagnostics)
