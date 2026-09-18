"""Shared fixtures for Home Assistant integration tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stirling_pdf.const import DOMAIN


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a Stirling PDF config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Stirling PDF (pdf.local)",
        data={
            CONF_URL: "http://pdf.local:8080",
            CONF_API_KEY: "stored-secret",
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def loaded_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    enable_custom_integrations: None,
) -> MockConfigEntry:
    """Set up a loaded Stirling PDF config entry."""
    with patch(
        "custom_components.stirling_pdf.api.StirlingPdfApiClient.async_get_status",
        new=AsyncMock(return_value={"status": "UP", "version": "2.14.3"}),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
