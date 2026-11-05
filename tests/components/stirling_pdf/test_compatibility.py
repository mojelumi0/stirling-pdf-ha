"""Selected-server release gates and explicit converter choices, with mocked HTTP."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_URL
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stirling_pdf.const import DOMAIN
from custom_components.stirling_pdf.operations import OPERATIONS
from custom_components.stirling_pdf.tools import ha_field_name, server_release

NEW_CONVERTERS = [
    name
    for name, operation in OPERATIONS.items()
    if "office_convert_since" in operation
]
ALL_CONVERTERS = [
    name
    for name, operation in OPERATIONS.items()
    if "useStirlingOfficeConvert" in operation["fields"]
]


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ({"version": "2.14.3"}, (2, 14, 3)),
        ({"version": "3.2.0"}, (3, 2, 0)),
        ({"version": "v3.3.0"}, (3, 3, 0)),
        ({"version": " 3.3.1 "}, (3, 3, 1)),
        ({"version": "3.3.0+build.123"}, (3, 3, 0)),
        ({"version": "4.0.0"}, (4, 0, 0)),
        ({"appVersion": "3.2.2"}, (3, 2, 2)),
        ({"version": "", "appVersion": "2.14.3"}, (2, 14, 3)),
        (None, None),
        ([], None),
        ({}, None),
        ({"version": 3}, None),
        ({"version": True}, None),
        ({"version": ["3.3.0"]}, None),
        ({"version": "unknown"}, None),
        ({"version": "3.3"}, None),
        ({"version": "3.3.0-rc.1"}, None),
        ({"version": "3.3.0-SNAPSHOT"}, None),
        ({"version": "3.3.0 (custom)"}, None),
        ({"version": "12345.1.0"}, None),
        ({"version": "3" * 1000}, None),
    ],
)
def test_server_release_is_bounded_and_does_not_guess_custom_versions(
    status: object, expected: tuple[int, int, int] | None
) -> None:
    assert server_release(status) == expected


@pytest.mark.parametrize(
    ("version", "error_key"),
    [
        ("3.3.0", "tool_removed"),
        ("v3.3.0", "tool_removed"),
        ("3.3.0+build", "tool_removed"),
        ("3.3.1", "tool_removed"),
        ("4.0.0", "tool_removed"),
        (None, "server_version_unknown"),
        ("unknown", "server_version_unknown"),
        ("3.3.0-rc.1", "server_version_unknown"),
    ],
)
async def test_removed_tool_stops_before_file_io_or_statistics(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    tmp_path: Path,
    version: str | None,
    error_key: str,
) -> None:
    coordinator = loaded_entry.runtime_data
    coordinator.data = {"status": "UP", "version": version}
    coordinator.record_operation("merge")
    before = (coordinator.jobs_processed, coordinator.last_operation_time)
    output = tmp_path / "existing.pdf"
    output.write_bytes(b"unchanged existing output")
    client = coordinator.client
    client.async_process = AsyncMock()
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
            "replace_text",
            {
                "file_path": "/not/allowed/input.pdf",
                "output_path": str(output),
                "overwrite": True,
                "edits": [],
            },
            blocking=True,
            return_response=True,
        )
    assert raised.value.translation_key == error_key
    read.assert_not_awaited()
    validate.assert_not_called()
    write.assert_not_awaited()
    client.async_process.assert_not_awaited()
    assert output.read_bytes() == b"unchanged existing output"
    assert (coordinator.jobs_processed, coordinator.last_operation_time) == before
    assert coordinator.last_operation == "merge"
    assert not hass.config_entries.flow.async_progress()


async def test_removed_tool_gate_uses_only_the_explicitly_selected_entry(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, tmp_path: Path
) -> None:
    newer = MockConfigEntry(
        domain=DOMAIN, title="New server", data={CONF_URL: "http://new.local:8080"}
    )
    newer.add_to_hass(hass)
    with patch(
        "custom_components.stirling_pdf.api.StirlingPdfApiClient.async_validate_connection",
        new=AsyncMock(return_value={"status": "UP", "version": "3.3.0"}),
    ):
        assert await hass.config_entries.async_setup(newer.entry_id)
        await hass.async_block_till_done()
    hass.config.allowlist_external_dirs.add(str(tmp_path))
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-synthetic-input")
    output = tmp_path / "result.pdf"
    older_client = loaded_entry.runtime_data.client
    older_client.async_process = AsyncMock(return_value=(200, b"%PDF-synthetic-result"))
    newer.runtime_data.client.async_process = AsyncMock()
    payload = {"file_path": str(source), "output_path": str(output), "edits": []}
    with pytest.raises(ServiceValidationError) as raised:
        await hass.services.async_call(
            DOMAIN,
            "replace_text",
            {**payload, "config_entry_id": newer.entry_id},
            blocking=True,
        )
    assert raised.value.translation_key == "tool_removed"
    assert not output.exists()
    assert (
        loaded_entry.runtime_data.jobs_processed
        == newer.runtime_data.jobs_processed
        == 0
    )
    await hass.services.async_call(
        DOMAIN,
        "replace_text",
        {**payload, "config_entry_id": loaded_entry.entry_id},
        blocking=True,
    )
    assert output.read_bytes() == b"%PDF-synthetic-result"
    assert source.read_bytes() == b"%PDF-synthetic-input"
    older_client.async_process.assert_awaited_once()
    newer.runtime_data.client.async_process.assert_not_awaited()
    assert loaded_entry.runtime_data.jobs_processed == 1
    assert newer.runtime_data.jobs_processed == 0


def _payload(name: str, source: Path, output: Path) -> dict:
    operation = OPERATIONS[name]
    data = {"file_path": str(source), "output_path": str(output)}
    for key, spec in operation["fields"].items():
        if spec["required"] and "default" not in spec:
            choices = spec.get("enum", ["test"])
            suffix = output.suffix.lstrip(".")
            data[ha_field_name(key)] = suffix if suffix in choices else choices[0]
    return data


@pytest.mark.parametrize("name", NEW_CONVERTERS)
@pytest.mark.parametrize(
    ("version", "error_key"),
    [("3.2.2", "tool_option_unsupported"), ("custom", "server_version_unknown")],
)
async def test_new_converter_choice_rejects_old_or_unknown_versions_before_upload(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    name: str,
    version: str,
    error_key: str,
) -> None:
    hass.config_entries.async_update_entry(
        loaded_entry, options={"enable_external_actions": True}
    )
    coordinator = loaded_entry.runtime_data
    coordinator.data = {"version": version}
    coordinator.client.async_process = AsyncMock()
    operation = OPERATIONS[name]
    data = _payload(
        name,
        Path("/not/allowed/input" + operation["inputExtensions"][0]),
        Path("/not/allowed/output" + operation["suffixes"][0]),
    )
    data["use_stirling_office_convert"] = True
    with (
        patch(
            "custom_components.stirling_pdf.tools._read_file", new_callable=AsyncMock
        ) as read,
        patch("custom_components.stirling_pdf._validate_output_path") as validate,
        pytest.raises(ServiceValidationError) as raised,
    ):
        await hass.services.async_call(DOMAIN, name, data, blocking=True)
    assert raised.value.translation_key == error_key
    read.assert_not_awaited()
    validate.assert_not_called()
    coordinator.client.async_process.assert_not_awaited()
    assert coordinator.jobs_processed == 0


@pytest.mark.parametrize("name", ALL_CONVERTERS)
@pytest.mark.parametrize("choice", [None, False, True])
async def test_all_converter_choices_are_explicit_and_keep_admin_opt_in_rules(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    tmp_path: Path,
    name: str,
    choice: bool | None,
) -> None:
    """Test routing/wire fields with mocked output, not converter rendering quality."""
    coordinator = loaded_entry.runtime_data
    coordinator.data = {"version": "3.3.0", "status": "UP"}
    hass.config_entries.async_update_entry(
        loaded_entry, options={"enable_external_actions": choice is True}
    )
    hass.config.allowlist_external_dirs.add(str(tmp_path))
    operation = OPERATIONS[name]
    source = tmp_path / ("input" + operation["inputExtensions"][0])
    source.write_bytes(b"synthetic converter input")
    suffix = operation["suffixes"][0]
    output = tmp_path / ("output" + suffix)
    data = _payload(name, source, output)
    if choice is not None:
        data["use_stirling_office_convert"] = choice
    result = {
        ".pdf": b"%PDF-synthetic-result",
        ".doc": b"\xd0\xcf\x11\xe0synthetic-result",
        ".ppt": b"\xd0\xcf\x11\xe0synthetic-result",
        ".xlsx": b"PK\x03\x04synthetic-result",
        ".epub": b"PK\x03\x04synthetic-result",
    }.get(suffix, b"Synthetic converter result\n")
    coordinator.client.async_process = AsyncMock(return_value=(200, result))
    with patch.object(
        hass.auth,
        "async_get_user",
        new=AsyncMock(return_value=SimpleNamespace(is_admin=choice is True)),
    ) as lookup:
        await hass.services.async_call(
            DOMAIN, name, data, blocking=True, context=Context(user_id="caller")
        )
    if choice is True:
        lookup.assert_awaited_once_with("caller")
    else:
        lookup.assert_not_awaited()
    wire = coordinator.client.async_process.await_args.args[2]
    assert wire["useStirlingOfficeConvert"] is (choice is True)
    assert output.read_bytes() == result
    assert source.read_bytes() == b"synthetic converter input"
    assert coordinator.jobs_processed == 1


async def test_unrestricted_action_still_works_without_a_parseable_version(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, tmp_path: Path
) -> None:
    loaded_entry.runtime_data.data = None
    hass.config.allowlist_external_dirs.add(str(tmp_path))
    source = tmp_path / "input.pdf"
    source.write_bytes(b"%PDF-input")
    output = tmp_path / "repaired.pdf"
    loaded_entry.runtime_data.client.async_process = AsyncMock(
        return_value=(200, b"%PDF-result")
    )
    await hass.services.async_call(
        DOMAIN,
        "repair",
        {"file_path": str(source), "output_path": str(output)},
        blocking=True,
    )
    assert output.read_bytes() == b"%PDF-result"
    assert loaded_entry.runtime_data.jobs_processed == 1
