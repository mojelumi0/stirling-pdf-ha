"""3.4.0 contracts, pre-upload failures and selected-server isolation."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from custom_components.stirling_pdf.const import DOMAIN
from custom_components.stirling_pdf.operations import OPERATIONS
from custom_components.stirling_pdf.tools import _validate_custom_page_size, tool_schema
from tests.ha_helpers import MockConfigEntry


async def _assert_rejected_before_io(hass, entry, name, fields, error_key):
    coordinator = entry.runtime_data
    coordinator.record_operation("merge")
    before = (
        coordinator.jobs_processed,
        coordinator.last_operation,
        coordinator.last_operation_time,
    )
    coordinator.client.async_process = AsyncMock()
    with (
        patch(
            "custom_components.stirling_pdf.tools._read_file", new_callable=AsyncMock
        ) as read,
        patch("custom_components.stirling_pdf._validate_output_path") as validate,
        patch(
            "custom_components.stirling_pdf._async_write_result", new_callable=AsyncMock
        ) as write,
        pytest.raises(ServiceValidationError) as raised,
    ):
        await hass.services.async_call(
            DOMAIN,
            name,
            {
                "file_path": "/not/allowlisted/input.pdf",
                "output_path": "/not/allowlisted/output.pdf",
                **fields,
            },
            blocking=True,
        )
    assert raised.value.translation_key == error_key
    read.assert_not_awaited()
    validate.assert_not_called()
    write.assert_not_awaited()
    coordinator.client.async_process.assert_not_awaited()
    assert (
        coordinator.jobs_processed,
        coordinator.last_operation,
        coordinator.last_operation_time,
    ) == before
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.parametrize("name", ["pdf_to_vector", "vector_to_pdf"])
@pytest.mark.parametrize("version", ["3.4.0", "v3.4.0+build.1", "3.4.1", "4.0.0"])
async def test_removed_vector_tools_reject_before_any_file_access(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, name, version
) -> None:
    loaded_entry.runtime_data.data = {"version": version}
    await _assert_rejected_before_io(hass, loaded_entry, name, {}, "tool_removed")


@pytest.mark.parametrize("name", ["pdf_to_vector", "vector_to_pdf"])
@pytest.mark.parametrize("version", [None, "custom", "3.4.0-rc.1"])
async def test_vector_tools_cannot_guess_unknown_or_prerelease_support(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, name, version
) -> None:
    loaded_entry.runtime_data.data = {"version": version}
    await _assert_rejected_before_io(
        hass, loaded_entry, name, {}, "server_version_unknown"
    )


@pytest.mark.parametrize("name", ["pdf_to_vector", "vector_to_pdf"])
@pytest.mark.parametrize("version", ["2.14.3", "3.2.0", "3.3.0"])
async def test_vector_tools_keep_legacy_support(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, tmp_path: Path, name, version
) -> None:
    operation = OPERATIONS[name]
    loaded_entry.runtime_data.data = {"version": version}
    hass.config.allowlist_external_dirs.add(str(tmp_path))
    source = tmp_path / ("input" + operation["inputExtensions"][0])
    source.write_bytes(b"synthetic input")
    output = tmp_path / ("result" + operation["suffixes"][0])
    result = b"%!PS-synthetic" if name == "pdf_to_vector" else b"%PDF-synthetic"
    loaded_entry.runtime_data.client.async_process = AsyncMock(
        return_value=(200, result)
    )
    await hass.services.async_call(
        DOMAIN,
        name,
        {"file_path": str(source), "output_path": str(output)},
        blocking=True,
    )
    assert output.read_bytes() == result
    assert source.read_bytes() == b"synthetic input"
    assert loaded_entry.runtime_data.jobs_processed == 1


@pytest.mark.parametrize(
    ("name", "fields"),
    [
        ("metadata", {"keep_omitted": True}),
        ("metadata", {"keep_omitted": False}),
        ("scale_pages", {"page_size": "CUSTOM"}),
        ("scale_pages", {"custom_width": 210}),
        ("scale_pages", {"custom_height": 297}),
        ("scale_pages", {"custom_unit": "mm"}),
    ],
)
@pytest.mark.parametrize("version", ["2.14.3", "3.3.0", "custom", None])
async def test_new_fields_require_a_known_supported_server_before_io(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, name, fields, version
) -> None:
    loaded_entry.runtime_data.data = {"version": version}
    error_key = (
        "server_version_unknown"
        if version in ("custom", None)
        else "tool_option_unsupported"
    )
    await _assert_rejected_before_io(hass, loaded_entry, name, fields, error_key)


@pytest.mark.parametrize(
    "fields",
    [
        {"page_size": "CUSTOM"},
        {"page_size": "CUSTOM", "custom_width": 210},
        {"page_size": "CUSTOM", "custom_height": 297},
        {"page_size": "CUSTOM", "custom_width": 0, "custom_height": 297},
        {"page_size": "CUSTOM", "custom_width": 210, "custom_height": 5081},
        {"page_size": "A4", "custom_width": 210, "custom_height": 297},
        {"custom_unit": "mm"},
        {
            "page_size": "CUSTOM",
            "custom_width": 201,
            "custom_height": 1,
            "custom_unit": "in",
        },
    ],
)
async def test_invalid_custom_size_does_not_read_upload_or_change_statistics(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, fields
) -> None:
    loaded_entry.runtime_data.data = {"version": "3.4.0"}
    await _assert_rejected_before_io(
        hass, loaded_entry, "scale_pages", fields, "invalid_custom_page_size"
    )


@pytest.mark.parametrize(
    ("unit", "minimum", "maximum"),
    [("mm", 25.4 / 24, 5080), ("cm", 2.54 / 24, 508), ("in", 1 / 24, 200)],
)
def test_custom_size_inclusive_bounds_and_out_of_bounds(unit, minimum, maximum) -> None:
    base = {"page_size": "CUSTOM", "custom_unit": unit}
    _validate_custom_page_size(
        {**base, "custom_width": minimum, "custom_height": maximum}
    )
    for width, height in ((minimum / 2, maximum), (minimum, maximum + 1)):
        with pytest.raises(ServiceValidationError):
            _validate_custom_page_size(
                {**base, "custom_width": width, "custom_height": height}
            )


@pytest.mark.parametrize("value", [True, -1, "invalid", float("inf"), float("nan")])
def test_custom_size_schema_rejects_invalid_numbers(value) -> None:
    with pytest.raises(vol.Invalid):
        tool_schema(OPERATIONS["scale_pages"])(
            {
                "file_path": "/input.pdf",
                "output_path": "/output.pdf",
                "page_size": "CUSTOM",
                "custom_width": value,
                "custom_height": 297,
            }
        )


@pytest.mark.parametrize("name", ["metadata", "scale_pages"])
@pytest.mark.parametrize("version", ["2.14.3", None])
async def test_existing_defaults_work_without_new_fields_on_an_old_server(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, tmp_path: Path, name, version
) -> None:
    hass.config.allowlist_external_dirs.add(str(tmp_path))
    source = tmp_path / "input.pdf"
    source.write_bytes(b"%PDF-input")
    output = tmp_path / "output.pdf"
    loaded_entry.runtime_data.data = {"version": version}
    client = loaded_entry.runtime_data.client
    client.async_process = AsyncMock(return_value=(200, b"%PDF-output"))
    await hass.services.async_call(
        DOMAIN,
        name,
        {"file_path": str(source), "output_path": str(output)},
        blocking=True,
    )
    fields = client.async_process.await_args.args[2]
    assert (
        not {"keepOmitted", "customWidth", "customHeight", "customUnit"} & fields.keys()
    )
    assert fields.get("deleteAll", False) is False
    assert fields.get("pageSize", "KEEP") == "KEEP"
    assert output.read_bytes() == b"%PDF-output"


@pytest.mark.parametrize(
    ("name", "fields", "supported_is_newer"),
    [
        ("pdf_to_vector", {}, False),
        ("metadata", {"keep_omitted": True, "title": "New title"}, True),
        (
            "scale_pages",
            {"page_size": "CUSTOM", "custom_width": 210, "custom_height": 297},
            True,
        ),
    ],
)
async def test_340_features_use_only_the_selected_server(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    tmp_path: Path,
    name,
    fields,
    supported_is_newer,
) -> None:
    newer = MockConfigEntry(
        domain=DOMAIN, title="New server", data={CONF_URL: "http://new.local:8080"}
    )
    newer.add_to_hass(hass)
    with patch(
        "custom_components.stirling_pdf.api.StirlingPdfApiClient.async_validate_connection",
        new=AsyncMock(return_value={"status": "UP", "version": "3.4.0"}),
    ):
        assert await hass.config_entries.async_setup(newer.entry_id)
        await hass.async_block_till_done()
    loaded_entry.runtime_data.data = {"version": "3.3.0"}
    supported = newer if supported_is_newer else loaded_entry
    unsupported = loaded_entry if supported_is_newer else newer
    hass.config.allowlist_external_dirs.add(str(tmp_path))
    source = tmp_path / "input.pdf"
    source.write_bytes(b"%PDF-input")
    suffix = ".pdf" if supported_is_newer else ".ps"
    output = tmp_path / ("result" + suffix)
    result = b"%PDF-output" if supported_is_newer else b"%!PS-output"
    supported.runtime_data.client.async_process = AsyncMock(return_value=(200, result))
    unsupported.runtime_data.client.async_process = AsyncMock()
    payload = {"file_path": str(source), "output_path": str(output), **fields}
    with pytest.raises(ServiceValidationError) as raised:
        await hass.services.async_call(
            DOMAIN,
            name,
            {**payload, "config_entry_id": unsupported.entry_id},
            blocking=True,
        )
    assert raised.value.translation_key == (
        "tool_option_unsupported" if supported_is_newer else "tool_removed"
    )
    assert not output.exists()
    await hass.services.async_call(
        DOMAIN,
        name,
        {**payload, "config_entry_id": supported.entry_id},
        blocking=True,
    )
    wire = supported.runtime_data.client.async_process.await_args.args[2]
    if name == "metadata":
        assert wire["keepOmitted"] is True
    elif name == "scale_pages":
        assert wire["customWidth"] == 210
        assert wire["customHeight"] == 297
        assert "customUnit" not in wire  # Leave the documented mm default to the API.
    assert output.read_bytes() == result
    assert source.read_bytes() == b"%PDF-input"
    assert supported.runtime_data.jobs_processed == 1
    assert unsupported.runtime_data.jobs_processed == 0
    unsupported.runtime_data.client.async_process.assert_not_awaited()
