"""Tests for Stirling PDF diagnostics."""

from __future__ import annotations

import json

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stirling_pdf.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_diagnostics_are_useful_and_redacted(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Test diagnostics include runtime details without private configuration."""
    loaded_entry.runtime_data.record_operation("merge")

    diagnostics = await async_get_config_entry_diagnostics(hass, loaded_entry)
    serialized = json.dumps(diagnostics)

    assert "stored-secret" not in serialized
    assert "pdf.local" not in serialized
    assert diagnostics["coordinator"]["last_update_success"] is True
    assert diagnostics["coordinator"]["status"] == {
        "status": "UP",
        "version": "2.14.3",
    }
    assert diagnostics["coordinator"]["jobs_processed"] == 1
    assert diagnostics["coordinator"]["last_operation"] == "merge"
    assert diagnostics["coordinator"]["last_operation_time"] is not None
