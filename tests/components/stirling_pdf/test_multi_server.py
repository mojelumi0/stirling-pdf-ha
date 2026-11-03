"""Multi-entry routing must never silently choose another server."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stirling_pdf import _get_coordinator
from custom_components.stirling_pdf.const import DOMAIN


async def test_two_entries_route_files_credentials_and_statistics_independently(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    tmp_path: Path,
) -> None:
    second = MockConfigEntry(
        domain=DOMAIN,
        title="Other server",
        data={CONF_URL: "http://other.local:8080", CONF_API_KEY: "other-secret"},
    )
    second.add_to_hass(hass)
    with patch(
        "custom_components.stirling_pdf.api.StirlingPdfApiClient.async_validate_connection",
        new=AsyncMock(return_value={"status": "UP"}),
    ):
        assert await hass.config_entries.async_setup(second.entry_id)
        await hass.async_block_till_done()
    assert _get_coordinator(hass, second.entry_id) is second.runtime_data
    assert second.runtime_data.client._headers()["X-API-KEY"] == "other-secret"
    assert loaded_entry.runtime_data.client._headers()["X-API-KEY"] == "stored-secret"
    with pytest.raises(ServiceValidationError) as error:
        _get_coordinator(hass)
    assert error.value.translation_key == "server_required"
    hass.config.allowlist_external_dirs.add(str(tmp_path))
    source = tmp_path / "a.pdf"
    source.write_bytes(b"%PDF-input")
    first_client = loaded_entry.runtime_data.client
    first_client.async_compress = AsyncMock(return_value=b"%PDF-first")
    second.runtime_data.client.async_compress = AsyncMock(return_value=b"%PDF-second")
    await hass.services.async_call(
        DOMAIN,
        "compress",
        {
            "config_entry_id": second.entry_id,
            "file_path": str(source),
            "output_path": str(tmp_path / "result.pdf"),
        },
        blocking=True,
    )
    first_client.async_compress.assert_not_awaited()
    assert (tmp_path / "result.pdf").read_bytes() == b"%PDF-second"
    assert loaded_entry.runtime_data.jobs_processed == 0
    assert second.runtime_data.jobs_processed == 1
    assert await hass.config_entries.async_unload(second.entry_id)
    with pytest.raises(ServiceValidationError) as error:
        _get_coordinator(hass, second.entry_id)
    assert error.value.translation_key == "entry_not_loaded"
    # A configured but unloaded server still makes untargeted routing ambiguous.
    assert loaded_entry.state is ConfigEntryState.LOADED
    with pytest.raises(ServiceValidationError):
        _get_coordinator(hass)
    assert _get_coordinator(hass, loaded_entry.entry_id) is loaded_entry.runtime_data


async def test_invalid_target_is_not_a_fallback(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    other = MockConfigEntry(domain="not_stirling_pdf", data={})
    other.add_to_hass(hass)
    for target in ("missing", other.entry_id):
        with pytest.raises(ServiceValidationError) as error:
            _get_coordinator(hass, target)
        assert error.value.translation_key == "invalid_server"
