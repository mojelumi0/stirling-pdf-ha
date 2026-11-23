"""3.5.0 format limits and removal of the legacy converter selector."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from custom_components.stirling_pdf.const import DOMAIN
from custom_components.stirling_pdf.operations import OPERATIONS
from custom_components.stirling_pdf.tools import _office_selector_retired
from tests.ha_helpers import MockConfigEntry

from .test_stirling_340 import _assert_rejected_before_io


@pytest.mark.parametrize("version", ["3.5.0", "v3.5.0+build.1", "3.5.1", "4.0.0"])
@pytest.mark.parametrize(
    "fields",
    [
        {"output_format": "doc", "output_path": "/output.doc"},
        {"output_format": "doc", "output_path": "/output.docx"},
        {"output_format": "docx", "output_path": "/output.DOC"},
    ],
)
async def test_removed_word_format_and_suffix_stop_before_io(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, version, fields
) -> None:
    loaded_entry.runtime_data.data = {"version": version}
    await _assert_rejected_before_io(
        hass, loaded_entry, "pdf_to_word", fields, "tool_format_removed"
    )


@pytest.mark.parametrize("version", [None, "custom", "3.5.0-rc.1"])
async def test_doc_output_cannot_guess_legacy_support(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, version
) -> None:
    loaded_entry.runtime_data.data = {"version": version}
    await _assert_rejected_before_io(
        hass,
        loaded_entry,
        "pdf_to_word",
        {"output_format": "doc", "output_path": "/output.doc"},
        "server_version_unknown",
    )


@pytest.mark.parametrize("zoom", [0, -1, 0.09, 8.01, 20])
@pytest.mark.parametrize(
    ("version", "error_key"),
    [("3.5.0", "tool_value_unsupported"), (None, "server_version_unknown")],
)
async def test_350_zoom_limits_apply_before_upload(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, zoom, version, error_key
) -> None:
    loaded_entry.runtime_data.data = {"version": version}
    await _assert_rejected_before_io(
        hass, loaded_entry, "html_to_pdf", {"zoom": zoom}, error_key
    )


@pytest.mark.parametrize(
    ("version", "zoom"),
    [("3.5.0", 0.1), ("3.5.0", 8), ("3.4.0", 20), (None, 1)],
)
async def test_html_zoom_boundaries_preserve_older_backend_behavior(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, tmp_path: Path, version, zoom
) -> None:
    coordinator = loaded_entry.runtime_data
    coordinator.data = {"version": version}
    hass.config.allowlist_external_dirs.add(str(tmp_path))
    source = tmp_path / "input.html"
    source.write_text("<p>SYNTHETIC</p>", encoding="utf-8")
    output = tmp_path / "output.pdf"
    coordinator.client.async_process = AsyncMock(return_value=(200, b"%PDF-output"))
    await hass.services.async_call(
        DOMAIN,
        "html_to_pdf",
        {"file_path": str(source), "output_path": str(output), "zoom": zoom},
        blocking=True,
    )
    wire = coordinator.client.async_process.await_args.args[2]
    assert wire["zoom"] == zoom
    assert ("useStirlingOfficeConvert" not in wire) is (version == "3.5.0")
    assert output.read_bytes() == b"%PDF-output"
    assert coordinator.jobs_processed == 1


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        (None, False),
        ("custom", False),
        ("3.5.0-rc.1", False),
        ("3.4.0", False),
        ("3.5.0", True),
        ("4.0.0", True),
    ],
)
def test_retired_selector_only_uses_a_recognized_selected_server(version, expected):
    coordinator = SimpleNamespace(data={"version": version})
    assert _office_selector_retired(coordinator, OPERATIONS["html_to_pdf"]) is expected
    assert _office_selector_retired(coordinator, OPERATIONS["repair"]) is False


async def test_doc_removal_is_isolated_between_old_and_new_entries(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, tmp_path: Path
) -> None:
    newer = MockConfigEntry(
        domain=DOMAIN, title="3.5 server", data={CONF_URL: "http://new.local:8080"}
    )
    newer.add_to_hass(hass)
    with patch(
        "custom_components.stirling_pdf.api.StirlingPdfApiClient.async_validate_connection",
        new=AsyncMock(return_value={"status": "UP", "version": "3.5.0"}),
    ):
        assert await hass.config_entries.async_setup(newer.entry_id)
        await hass.async_block_till_done()
    loaded_entry.runtime_data.data = {"version": "3.4.0"}
    hass.config.allowlist_external_dirs.add(str(tmp_path))
    source = tmp_path / "input.pdf"
    source.write_bytes(b"%PDF-input")
    output = tmp_path / "result.doc"
    payload = {
        "file_path": str(source),
        "output_path": str(output),
        "output_format": "doc",
    }
    result = b"\xd0\xcf\x11\xe0synthetic-doc"
    loaded_entry.runtime_data.client.async_process = AsyncMock(
        return_value=(200, result)
    )
    newer.runtime_data.client.async_process = AsyncMock()
    with pytest.raises(ServiceValidationError) as raised:
        await hass.services.async_call(
            DOMAIN,
            "pdf_to_word",
            {**payload, "config_entry_id": newer.entry_id},
            blocking=True,
        )
    assert raised.value.translation_key == "tool_format_removed"
    assert not output.exists()
    await hass.services.async_call(
        DOMAIN,
        "pdf_to_word",
        {**payload, "config_entry_id": loaded_entry.entry_id},
        blocking=True,
    )
    assert output.read_bytes() == result
    assert source.read_bytes() == b"%PDF-input"
    assert loaded_entry.runtime_data.jobs_processed == 1
    assert newer.runtime_data.jobs_processed == 0
    newer.runtime_data.client.async_process.assert_not_awaited()
