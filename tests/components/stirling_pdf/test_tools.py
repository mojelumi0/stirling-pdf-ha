"""Additional tool contracts, output validation and opt-in safety."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import voluptuous as vol
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stirling_pdf.api import (
    StirlingPdfApiError,
    StirlingPdfAuthError,
    StirlingPdfPermissionError,
)
from custom_components.stirling_pdf.const import DOMAIN
from custom_components.stirling_pdf.operations import OPERATIONS
from custom_components.stirling_pdf.tools import (
    _read_file,
    async_handle_tool,
    field_validator,
    tool_schema,
    validate_remote_url,
    validate_result,
)


def _coordinator(options=None):
    return SimpleNamespace(
        config_entry=SimpleNamespace(
            options=options or {}, entry_id="test-entry", async_start_reauth=MagicMock()
        ),
        client=SimpleNamespace(async_process=AsyncMock()),
        record_operation=MagicMock(),
    )


def _call(hass, name, data, response=True):
    return ServiceCall(
        hass,
        DOMAIN,
        name,
        tool_schema(OPERATIONS[name])(data),
        return_response=response,
    )


def _result(suffix):
    return {
        ".pdf": b"%PDF-result",
        ".zip": b"PK\x03\x04result",
        ".json": b'{"result":true}',
        ".png": b"\x89PNG\r\n\x1a\nresult",
        ".doc": b"\xd0\xcf\x11\xe0result",
        ".ppt": b"\xd0\xcf\x11\xe0result",
        ".xlsx": b"PK\x03\x04result",
        ".epub": b"PK\x03\x04result",
        ".cbr": b"Rar!result",
        ".cbz": b"PK\x03\x04result",
        ".ps": b"%!PSresult",
    }.get(suffix, b"Text result\n")


@pytest.mark.parametrize("name", OPERATIONS)
async def test_each_contract_can_be_validated_and_executed(
    hass: HomeAssistant, tmp_path: Path, name: str
) -> None:
    """Contract/handler coverage, explicitly not a real-server validation."""
    operation = OPERATIONS[name]
    hass.config.allowlist_external_dirs.add(str(tmp_path))
    payload = {}
    if operation["inputExtensions"]:
        source = tmp_path / ("input" + operation["inputExtensions"][0])
        source.write_bytes(b"%PDF-synthetic-input")
        payload["file_paths" if operation["multiple"] else "file_path"] = (
            [str(source)] if operation["multiple"] else str(source)
        )
    for key, spec in operation["files"].items():
        # Include optional parts too, to exercise mixed upload field names.
        source = tmp_path / (key + spec["extensions"][0])
        source.write_bytes(b"synthetic extra file")
        payload[key] = [str(source)] if spec["multiple"] else str(source)
    for key, spec in operation["fields"].items():
        if "default" in spec:
            continue
        payload[key] = (
            spec["enum"][0]
            if "enum" in spec
            else {
                "json": {},
                "array": [1] if spec.get("items") == "integer" else ["test"],
                "integer": 1,
                "number": 1,
                "boolean": False,
            }.get(spec["type"], "test")
        )
    if name == "url_to_pdf":
        payload["urlInput"] = "https://allowed.example/page"
    if name == "timestamp":
        payload["tsaUrl"] = "https://allowed.example/tsa"
    suffix = operation["suffixes"][0]
    payload["output_path"] = str(tmp_path / ("result" + suffix))
    coordinator = _coordinator(
        {
            "enable_sensitive_actions": True,
            "enable_external_actions": True,
            "enable_ai_actions": True,
            "allowed_url_hosts": "allowed.example",
        }
    )
    coordinator.client.async_process.return_value = (200, _result(suffix))
    validate = MagicMock()
    write = AsyncMock()
    response = await async_handle_tool(
        _call(hass, name, payload), coordinator, validate, write
    )
    assert response["operation"] == name
    assert response["config_entry_id"] == "test-entry"
    coordinator.record_operation.assert_called_once_with(name)
    args = coordinator.client.async_process.await_args.args
    assert args[0] == operation["endpoint"]
    assert args[4] == operation["primary"]
    assert [part[0] for part in args[3]] == list(operation["files"])
    write.assert_awaited_once()


@pytest.mark.parametrize(
    ("spec", "value", "expected"),
    [
        ({"type": "boolean"}, "true", True),
        ({"type": "integer"}, "2", 2),
        ({"type": "number"}, "2.5", 2.5),
        ({"type": "array", "items": "integer"}, [1, "2"], [1, 2]),
        ({"type": "json"}, {"a": 1}, {"a": 1}),
    ],
)
def test_field_types(spec, value, expected) -> None:
    assert field_validator(spec)(value) == expected


@pytest.mark.parametrize(
    ("spec", "value"),
    [
        ({"type": "number"}, float("inf")),
        ({"type": "integer", "minimum": 1}, 0),
        ({"type": "string", "maxLength": 2}, "long"),
        ({"type": "string", "enum": ["A"]}, "B"),
        ({"type": "json"}, "untyped JSON string"),
    ],
)
def test_field_validation_rejects_invalid_values(spec, value) -> None:
    with pytest.raises(vol.Invalid):
        field_validator(spec)(value)


@pytest.mark.parametrize(
    "url",
    [
        "https://unlisted.example",
        "file:///etc/passwd",
        "http://user:pass@allowed.example",
        "http://[bad",
    ],
)
def test_network_tools_require_explicit_hosts(url) -> None:
    with pytest.raises(ServiceValidationError):
        validate_remote_url(url, "allowed.example")


def test_network_host_matching_is_exact() -> None:
    validate_remote_url(
        "https://ALLOWED.example/path", " allowed.example, other.example "
    )
    with pytest.raises(ServiceValidationError):
        validate_remote_url("https://sub.allowed.example", "allowed.example")


@pytest.mark.parametrize(
    ("content", "suffix"),
    [
        (b"%PDF-result", ".pdf"),
        (b"PK\x03\x04test", ".docx"),
        (b"\xff\xd8\xfftest", ".jpg"),
        (b"GIF89atest", ".gif"),
        (b"II*\0test", ".tiff"),
        (b"BMtest", ".bmp"),
        (b"RIFF1234WEBPtest", ".webp"),
        (b"{\\rtf test}", ".rtf"),
        (b"\x1btest", ".pcl"),
        (b"BOOKMOBItest", ".azw3"),
        (b"plain text", ".txt"),
        (b'{"ok":true}', ".json"),
    ],
)
def test_supported_output_containers(content, suffix) -> None:
    validate_result(content, suffix)


@pytest.mark.parametrize(
    ("content", "suffix"),
    [
        (b"<html>Login</html>", ".pdf"),
        (b"%PDF-input", ".zip"),
        (b"not json", ".json"),
        (b"\xffinvalid utf8", ".txt"),
        (b"PK\x03\x04zip", ".txt"),
        (b"unknown", ".exe"),
    ],
)
def test_bad_outputs_cannot_replace_files(content, suffix) -> None:
    with pytest.raises(StirlingPdfApiError):
        validate_result(content, suffix)


async def test_new_action_uses_the_real_registry_atomic_writer_and_statistics(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    tmp_path: Path,
) -> None:
    hass.config.allowlist_external_dirs.add(str(tmp_path))
    source = tmp_path / "a.pdf"
    source.write_bytes(b"%PDF-input")
    loaded_entry.runtime_data.client.async_process = AsyncMock(
        return_value=(200, b"%PDF-rotated")
    )
    payload = {
        "file_path": str(source),
        "output_path": str(tmp_path / "out.pdf"),
        "angle": 90,
    }
    await hass.services.async_call(DOMAIN, "rotate", payload, blocking=True)
    assert (tmp_path / "out.pdf").read_bytes() == b"%PDF-rotated"
    assert loaded_entry.runtime_data.jobs_processed == 1
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "rotate", payload, blocking=True)
    assert loaded_entry.runtime_data.client.async_process.await_count == 1


async def test_opt_in_is_checked_before_files_or_network(hass: HomeAssistant) -> None:
    coordinator = _coordinator()
    call = _call(
        hass,
        "remove_password",
        {"file_path": "/not/allowed.pdf", "output_path": "/not/out.pdf"},
    )
    with pytest.raises(ServiceValidationError) as error:
        await async_handle_tool(call, coordinator, MagicMock(), AsyncMock())
    assert error.value.translation_key == "action_group_disabled"
    coordinator.client.async_process.assert_not_awaited()
    call = _call(
        hass,
        "pdf_to_word",
        {
            "file_path": "/not/allowed.pdf",
            "output_path": "/not/out.docx",
            "outputFormat": "docx",
            "useStirlingOfficeConvert": True,
        },
    )
    with pytest.raises(ServiceValidationError):
        await async_handle_tool(call, coordinator, MagicMock(), AsyncMock())
    coordinator.client.async_process.assert_not_awaited()


async def test_opt_in_groups_use_home_assistant_admin_service_permissions(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    from unittest.mock import patch

    with patch.object(
        hass.auth,
        "async_get_user",
        new=AsyncMock(return_value=SimpleNamespace(is_admin=False)),
    ):
        with pytest.raises(Unauthorized):
            await hass.services.async_call(
                DOMAIN,
                "remove_password",
                {"file_path": "/not/allowed.pdf", "output_path": "/not/out.pdf"},
                blocking=True,
                context=Context(user_id="non-admin"),
            )


@pytest.mark.parametrize(
    ("error", "key", "reauth"),
    [
        (FileExistsError(), "output_exists", False),
        (OSError("disk failure"), "file_error", False),
        (StirlingPdfAuthError(), "authentication_failed", True),
        (StirlingPdfPermissionError(), "tool_forbidden", False),
        (StirlingPdfApiError("unsupported"), "processing_failed", False),
    ],
)
async def test_errors_do_not_increment_statistics(
    hass: HomeAssistant, tmp_path: Path, error: Exception, key: str, reauth: bool
) -> None:
    hass.config.allowlist_external_dirs.add(str(tmp_path))
    source = tmp_path / "a.pdf"
    source.write_bytes(b"%PDF-input")
    coordinator = _coordinator()
    coordinator.client.async_process.side_effect = error
    call = _call(
        hass,
        "repair",
        {"file_path": str(source), "output_path": str(tmp_path / "out.pdf")},
    )
    with pytest.raises(HomeAssistantError) as raised:
        await async_handle_tool(call, coordinator, MagicMock(), AsyncMock())
    assert raised.value.translation_key == key
    assert coordinator.config_entry.async_start_reauth.called is reauth
    coordinator.record_operation.assert_not_called()


async def test_optional_json_and_false_filter_responses(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    hass.config.allowlist_external_dirs.add(str(tmp_path))
    source = tmp_path / "a.pdf"
    source.write_bytes(b"%PDF-input")
    coordinator = _coordinator()
    write = AsyncMock()
    coordinator.client.async_process.return_value = (204, b"")
    call = _call(hass, "check_contains_image", {"file_path": str(source)})
    response = await async_handle_tool(call, coordinator, MagicMock(), write)
    assert response["matches"] is False
    assert "output_path" not in response
    write.assert_not_awaited()
    coordinator.client.async_process.return_value = (200, b'{"pageCount":3}')
    response = await async_handle_tool(
        _call(hass, "analyze_page_count", {"file_path": str(source)}),
        coordinator,
        MagicMock(),
        write,
    )
    assert response["result"] == {"pageCount": 3}
    assert (
        await async_handle_tool(
            _call(hass, "analyze_page_count", {"file_path": str(source)}, False),
            coordinator,
            MagicMock(),
            write,
        )
        is None
    )
    coordinator.client.async_process.return_value = (200, b"%PDF-matched")
    response = await async_handle_tool(call, coordinator, MagicMock(), write)
    assert response["matches"] is True


@pytest.mark.parametrize(
    ("service", "status", "content"),
    [
        ("analyze_page_count", 200, b"bad-json"),
        ("analyze_page_count", 200, b" " * (4 * 1024 * 1024 + 1)),
        ("check_contains_image", 202, b""),
        ("repair", 200, b"not a PDF"),
    ],
)
async def test_invalid_server_results_are_not_saved(
    hass: HomeAssistant, tmp_path: Path, service: str, status: int, content: bytes
) -> None:
    hass.config.allowlist_external_dirs.add(str(tmp_path))
    source = tmp_path / "a.pdf"
    source.write_bytes(b"%PDF-input")
    coordinator = _coordinator()
    coordinator.client.async_process.return_value = (status, content)
    write = AsyncMock()
    with pytest.raises(HomeAssistantError):
        await async_handle_tool(
            _call(
                hass,
                service,
                {
                    "file_path": str(source),
                    "output_path": str(
                        tmp_path / ("out" + OPERATIONS[service]["suffixes"][0])
                    ),
                },
            ),
            coordinator,
            MagicMock(),
            write,
        )
    write.assert_not_awaited()
    coordinator.record_operation.assert_not_called()


async def test_path_suffix_limits_and_missing_tsa(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    with pytest.raises(ServiceValidationError):
        await _read_file(hass, str(tmp_path / "a.pdf"), [".pdf"])
    hass.config.allowlist_external_dirs.add(str(tmp_path))
    with pytest.raises(ServiceValidationError):
        await _read_file(hass, str(tmp_path / "a.exe"), [".pdf"])
    coordinator = _coordinator({"enable_external_actions": True})
    with pytest.raises(ServiceValidationError) as error:
        await async_handle_tool(
            _call(
                hass,
                "timestamp",
                {
                    "file_path": str(tmp_path / "a.pdf"),
                    "output_path": str(tmp_path / "out.pdf"),
                },
            ),
            coordinator,
            MagicMock(),
            AsyncMock(),
        )
    assert error.value.translation_key == "remote_host_not_allowed"
    with pytest.raises(ServiceValidationError):
        await async_handle_tool(
            _call(
                hass,
                "repair",
                {
                    "file_path": str(tmp_path / "a.pdf"),
                    "output_path": str(tmp_path / "out.zip"),
                },
            ),
            coordinator,
            MagicMock(),
            AsyncMock(),
        )


async def test_bounded_inputs_and_invalid_structured_fields(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    hass.config.allowlist_external_dirs.add(str(tmp_path))
    source = tmp_path / "a.pdf"
    source.write_bytes(b"%PDF-input")
    coordinator = _coordinator()
    # Small limits exercise the exact production branches without huge fixtures.
    from unittest.mock import patch

    with patch("custom_components.stirling_pdf.tools._MAX_INPUT_BYTES", 3):
        with pytest.raises(ServiceValidationError):
            await _read_file(hass, str(source), [".pdf"])
    for structured in ({"value": "x" * 30}, {"value": float("nan")}):
        with patch("custom_components.stirling_pdf.tools._MAX_JSON_BYTES", 10):
            with pytest.raises(HomeAssistantError):
                await async_handle_tool(
                    _call(
                        hass,
                        "form_fill",
                        {
                            "file_path": str(source),
                            "output_path": str(tmp_path / "out.pdf"),
                            "data": structured,
                        },
                    ),
                    coordinator,
                    MagicMock(),
                    AsyncMock(),
                )
    image = tmp_path / "b.png"
    image.write_bytes(b"img")
    with patch("custom_components.stirling_pdf.tools._MAX_FILES", 1):
        with pytest.raises(ServiceValidationError):
            await async_handle_tool(
                _call(
                    hass,
                    "add_image",
                    {
                        "file_path": str(source),
                        "output_path": str(tmp_path / "out.pdf"),
                        "imageFile": str(image),
                    },
                ),
                coordinator,
                MagicMock(),
                AsyncMock(),
            )
