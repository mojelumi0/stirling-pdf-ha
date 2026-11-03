"""Explicit contracts and safe local file handling for additional PDF tools."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
    UnknownUser,
)
from homeassistant.helpers import config_validation as cv
from yarl import URL

from .api import StirlingPdfApiError, StirlingPdfAuthError, StirlingPdfPermissionError
from .const import (
    CONF_AI_ACTIONS,
    CONF_ALLOWED_URL_HOSTS,
    CONF_EXTERNAL_ACTIONS,
    CONF_SENSITIVE_ACTIONS,
    DOMAIN,
)
from .coordinator import StirlingPdfCoordinator
from .operations import OPERATIONS

_GROUP_OPTIONS = {
    "sensitive": CONF_SENSITIVE_ACTIONS,
    "external": CONF_EXTERNAL_ACTIONS,
    "ai": CONF_AI_ACTIONS,
}
_MAX_FILES = 32
_MAX_INPUT_BYTES = 64 * 1024 * 1024
_MAX_JSON_BYTES = 4 * 1024 * 1024


def ha_field_name(api_name: str) -> str:
    """Use HA-compatible public names without changing multipart API names."""
    words = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", api_name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", words).lower()


def integer_value(value: Any) -> int:
    """Accept whole numbers without silently truncating floats or booleans."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise vol.Invalid("An integer is required")
    if isinstance(value, float) and (
        not math.isfinite(value) or not value.is_integer()
    ):
        raise vol.Invalid("An integer is required")
    try:
        return int(value)
    except (ValueError, OverflowError) as err:
        raise vol.Invalid("An integer is required") from err


def _number_value(value: Any) -> float:
    """Reject booleans, non-finite values and overflowing numeric conversions."""
    if isinstance(value, bool):
        raise vol.Invalid("A finite number is required")
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError) as err:
        raise vol.Invalid("A finite number is required") from err
    if not math.isfinite(number):
        raise vol.Invalid("A finite number is required")
    return number


def field_validator(spec: dict[str, Any]) -> Callable:
    """Build validation from a fixed, locally reviewed field contract."""
    kind = spec["type"]
    if kind == "json":
        return vol.Any(dict, list)
    if kind == "array":
        item = field_validator({"type": spec["items"]})
        return vol.All(cv.ensure_list, [item], vol.Length(max=1024))
    if kind == "boolean":
        validator = cv.boolean
    elif kind in ("number", "integer"):
        validator = vol.All(
            integer_value if kind == "integer" else _number_value,
            vol.Range(min=spec.get("minimum"), max=spec.get("maximum")),
        )
    else:
        validator = vol.All(
            cv.string,
            vol.Length(min=spec.get("minLength", 0), max=spec.get("maxLength", 65536)),
        )
    return vol.All(validator, vol.In(spec["enum"])) if "enum" in spec else validator


def tool_schema(operation: dict[str, Any]) -> vol.Schema:
    """Expose named fields, never an arbitrary endpoint or untyped payload."""
    fields: dict[Any, Any] = {
        vol.Optional("config_entry_id"): cv.string,
        vol.Optional("overwrite", default=False): cv.boolean,
    }
    if operation["inputExtensions"]:
        key = "file_paths" if operation["multiple"] else "file_path"
        fields[vol.Required(key)] = (
            vol.All(cv.ensure_list, [cv.string], vol.Length(min=1, max=_MAX_FILES))
            if operation["multiple"]
            else cv.string
        )
    marker = vol.Optional if operation["output"] in ("json", "filter") else vol.Required
    fields[marker("output_path")] = cv.string
    for name, spec in operation["files"].items():
        marker = vol.Required if spec["required"] else vol.Optional
        fields[marker(ha_field_name(name))] = (
            vol.All(cv.ensure_list, [cv.string], vol.Length(min=1, max=_MAX_FILES))
            if spec["multiple"]
            else cv.string
        )
    for name, spec in operation["fields"].items():
        marker = vol.Required if spec["required"] else vol.Optional
        key = (
            marker(ha_field_name(name), default=spec["default"])
            if "default" in spec
            else marker(ha_field_name(name))
        )
        fields[key] = field_validator(spec)
    return vol.Schema(fields)


def validate_remote_url(value: str, allowed_hosts: str) -> None:
    """Require explicit permission for the initial server-side fetch host.

    This is not an SSRF sandbox: server-side redirects, DNS and embedded resources
    must also be controlled by the Stirling PDF deployment/network administrator.
    """
    try:
        url = URL(value)
        hosts = {
            host.strip().casefold() for host in allowed_hosts.split(",") if host.strip()
        }
        valid = (
            url.scheme in {"http", "https"}
            and url.host is not None
            and url.user is None
            and url.password is None
            and url.host.casefold() in hosts
        )
    except ValueError:
        valid = False
    if not valid:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="remote_host_not_allowed"
        )


async def _read_file(
    hass: HomeAssistant, value: str, suffixes: list[str], remaining: int | None = None
) -> tuple[str, bytes]:
    """Read only allowlisted, bounded local files on the executor."""

    def read() -> tuple[str, bytes]:
        path = Path(value)
        if not path.is_absolute() or not hass.config.is_allowed_path(value):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="path_not_allowed",
                translation_placeholders={"path": value},
            )
        if path.suffix.lower() not in suffixes:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_extension",
                translation_placeholders={
                    "path": value,
                    "extension": ", ".join(suffixes),
                },
            )
        with path.open("rb") as source:
            limit = (
                min(_MAX_INPUT_BYTES, remaining)
                if remaining is not None
                else _MAX_INPUT_BYTES
            )
            content = source.read(limit + 1)
        if len(content) > limit:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="input_too_large"
            )
        return path.name, content

    return await hass.async_add_executor_job(read)


def validate_result(content: bytes, suffix: str) -> None:
    """Check the selected output container before creating or replacing a file."""
    if suffix == ".json" and len(content) > _MAX_JSON_BYTES:
        raise StirlingPdfApiError("Tool JSON response exceeds the response limit")
    zip_file = content.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"))
    checks = {
        ".pdf": b"%PDF-" in content[:1024],
        ".zip": zip_file,
        ".docx": zip_file,
        ".xlsx": zip_file,
        ".pptx": zip_file,
        ".odt": zip_file,
        ".odp": zip_file,
        ".epub": zip_file,
        ".cbz": zip_file,
        ".xps": zip_file,
        ".png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": content.startswith(b"\xff\xd8\xff"),
        ".jpeg": content.startswith(b"\xff\xd8\xff"),
        ".gif": content.startswith((b"GIF87a", b"GIF89a")),
        ".tif": content.startswith((b"II*\0", b"MM\0*")),
        ".tiff": content.startswith((b"II*\0", b"MM\0*")),
        ".bmp": content.startswith(b"BM"),
        ".webp": content.startswith(b"RIFF") and content[8:12] == b"WEBP",
        ".doc": content.startswith(b"\xd0\xcf\x11\xe0"),
        ".ppt": content.startswith(b"\xd0\xcf\x11\xe0"),
        ".cbr": content.startswith(b"Rar!"),
        ".rtf": content.lstrip().startswith(b"{\\rtf"),
        ".ps": content.startswith(b"%!PS"),
        ".eps": content.startswith(b"%!PS"),
        ".pcl": content.startswith(b"\x1b"),
        ".azw3": b"BOOKMOBI" in content[:80],
    }
    if suffix in (".txt", ".csv", ".md", ".xml", ".html", ".js", ".json"):
        try:
            content.decode("utf-8-sig")
            valid = bool(content) and not content.startswith((b"%PDF-", b"PK\x03\x04"))
            if suffix == ".json":
                json.loads(content)
        except UnicodeError, ValueError:
            valid = False
    else:
        valid = checks.get(suffix, False)
    if not valid:
        raise StirlingPdfApiError(
            "The tool response does not match the selected output extension"
        )


async def async_handle_tool(
    call: ServiceCall,
    coordinator: StirlingPdfCoordinator,
    validate_output: Callable[..., Path],
    write_result: Callable[..., Awaitable[None]],
) -> ServiceResponse | None:
    """Run a reviewed tool for exactly one selected config entry."""
    operation = OPERATIONS[call.service]
    entry = coordinator.config_entry
    assert entry is not None
    option = _GROUP_OPTIONS.get(operation["group"])
    if option and not entry.options.get(option, False):
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="action_group_disabled"
        )
    if call.data.get("use_stirling_office_convert"):
        if not entry.options.get(CONF_EXTERNAL_ACTIONS, False):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="action_group_disabled"
            )
        # Match HA's admin-service rules without restricting local conversions.
        if call.context.user_id:
            user = await call.hass.auth.async_get_user(call.context.user_id)
            if user is None:
                raise UnknownUser(context=call.context)
            if not user.is_admin:
                raise Unauthorized(context=call.context)
    output_path = call.data.get("output_path")
    suffix = Path(output_path).suffix.lower() if output_path else ""
    overwrite = call.data["overwrite"]
    try:
        if output_path:
            if suffix not in operation["suffixes"]:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_extension",
                    translation_placeholders={
                        "path": output_path,
                        "extension": ", ".join(operation["suffixes"]),
                    },
                )
            await call.hass.async_add_executor_job(
                validate_output, call.hass, output_path, suffix, overwrite
            )
        for name in ("url_input", "tsa_url"):
            if name in call.data:
                validate_remote_url(
                    call.data[name], entry.options.get(CONF_ALLOWED_URL_HOSTS, "")
                )
        # Never silently use a vendor timestamp service as an unapproved host.
        if call.service == "timestamp" and not call.data.get("tsa_url"):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="remote_host_not_allowed"
            )
        files = []
        remaining = _MAX_INPUT_BYTES
        if operation["inputExtensions"]:
            paths = (
                call.data["file_paths"]
                if operation["multiple"]
                else [call.data["file_path"]]
            )
            for path in paths:
                files.append(
                    await _read_file(
                        call.hass, path, operation["inputExtensions"], remaining
                    )
                )
                remaining -= len(files[-1][1])
        extra_files = []
        for name, spec in operation["files"].items():
            public_name = ha_field_name(name)
            if public_name in call.data:
                paths = (
                    call.data[public_name]
                    if spec["multiple"]
                    else [call.data[public_name]]
                )
                for path in paths:
                    filename, content = await _read_file(
                        call.hass, path, spec["extensions"], remaining
                    )
                    extra_files.append((name, filename, content))
                    remaining -= len(content)
        if (
            len(files) + len(extra_files) > _MAX_FILES
            or sum(len(item[-1]) for item in [*files, *extra_files]) > _MAX_INPUT_BYTES
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="input_too_large"
            )
        data = {}
        for name, spec in operation["fields"].items():
            public_name = ha_field_name(name)
            if public_name in call.data:
                value = call.data[public_name]
                if spec["type"] == "json":
                    value = json.dumps(value, allow_nan=False)
                    if len(value.encode()) > _MAX_JSON_BYTES:
                        raise ServiceValidationError(
                            translation_domain=DOMAIN, translation_key="input_too_large"
                        )
                data[name] = value
        status, result = await coordinator.client.async_process(
            operation["endpoint"],
            files,
            data,
            extra_files,
            operation["primary"],
        )
        response: ServiceResponse = {
            "operation": call.service,
            "config_entry_id": entry.entry_id,
            "output_size": len(result),
            "input_count": len(files) + len(extra_files),
        }
        if operation["output"] == "filter":
            if status not in (200, 204):
                raise StirlingPdfApiError("Unexpected filter response")
            response["matches"] = status == 200
        elif operation["output"] == "json":
            if len(result) > _MAX_JSON_BYTES:
                raise StirlingPdfApiError(
                    "Tool JSON response exceeds the response limit"
                )
            try:
                response["result"] = json.loads(result)
            except (UnicodeError, ValueError) as err:
                raise StirlingPdfApiError("The tool returned invalid JSON") from err
        if operation["output"] != "filter" or status != 204:
            # Even without a saved filter output, a match must be a real PDF.
            validate_result(result, suffix or operation["suffixes"][0])
            if output_path:
                await write_result(call.hass, output_path, result, suffix, overwrite)
                response["output_path"] = output_path
    except ServiceValidationError:
        raise
    except FileExistsError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="output_exists",
            translation_placeholders={"path": output_path},
        ) from err
    except StirlingPdfAuthError as err:
        entry.async_start_reauth(call.hass)
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="authentication_failed"
        ) from err
    except StirlingPdfPermissionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="tool_forbidden"
        ) from err
    except (StirlingPdfApiError, ValueError, TypeError) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="processing_failed",
            translation_placeholders={
                "error": str(err)
                if isinstance(err, StirlingPdfApiError)
                else "Invalid structured input"
            },
        ) from err
    except OSError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="file_error",
            translation_placeholders={"error": str(err)},
        ) from err
    coordinator.record_operation(call.service)
    return response if call.return_response else None
