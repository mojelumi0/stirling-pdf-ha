"""The Stirling PDF integration."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import cast

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_URL, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import StirlingPdfApiClient, StirlingPdfApiError, StirlingPdfAuthError
from .const import (
    ATTR_FILE_PATH,
    ATTR_FILE_PATHS,
    ATTR_LANGUAGES,
    ATTR_OPTIMIZE_LEVEL,
    ATTR_OUTPUT_PATH,
    ATTR_OVERWRITE,
    ATTR_PAGE_NUMBERS,
    DEFAULT_OCR_LANGUAGES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SERVICE_COMPRESS,
    SERVICE_MERGE,
    SERVICE_OCR,
    SERVICE_SPLIT,
)
from .coordinator import StirlingPdfCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

type StirlingPdfConfigEntry = ConfigEntry[StirlingPdfCoordinator]

_LANGUAGE_SPLIT_PATTERN = re.compile(r"[,+\s]+")
_LANGUAGE_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

_MERGE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_FILE_PATHS): vol.All(
            cv.ensure_list,
            [cv.string],
            vol.Length(min=2),
        ),
        vol.Required(ATTR_OUTPUT_PATH): cv.string,
        vol.Optional(ATTR_OVERWRITE, default=False): cv.boolean,
    }
)
_SPLIT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_FILE_PATH): cv.string,
        vol.Required(ATTR_PAGE_NUMBERS): vol.All(cv.string, vol.Length(min=1)),
        vol.Required(ATTR_OUTPUT_PATH): cv.string,
        vol.Optional(ATTR_OVERWRITE, default=False): cv.boolean,
    }
)
_OCR_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_FILE_PATH): cv.string,
        vol.Optional(ATTR_LANGUAGES, default=DEFAULT_OCR_LANGUAGES): vol.All(
            cv.ensure_list,
            [cv.string],
            vol.Length(min=1),
        ),
        vol.Required(ATTR_OUTPUT_PATH): cv.string,
        vol.Optional(ATTR_OVERWRITE, default=False): cv.boolean,
    }
)
_COMPRESS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_FILE_PATH): cv.string,
        vol.Optional(ATTR_OPTIMIZE_LEVEL, default=5): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=9)
        ),
        vol.Required(ATTR_OUTPUT_PATH): cv.string,
        vol.Optional(ATTR_OVERWRITE, default=False): cv.boolean,
    }
)

_SERVICE_SCHEMAS = {
    SERVICE_MERGE: _MERGE_SCHEMA,
    SERVICE_SPLIT: _SPLIT_SCHEMA,
    SERVICE_OCR: _OCR_SCHEMA,
    SERVICE_COMPRESS: _COMPRESS_SCHEMA,
}


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up service actions so automations can always be validated."""
    for service, schema in _SERVICE_SCHEMAS.items():
        hass.services.async_register(
            DOMAIN,
            service,
            _async_handle_action,
            schema=schema,
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: StirlingPdfConfigEntry) -> bool:
    """Set up Stirling PDF from a config entry."""
    client = StirlingPdfApiClient(
        async_get_clientsession(hass),
        entry.data[CONF_URL],
        entry.data.get(CONF_API_KEY),
    )
    coordinator = StirlingPdfCoordinator(hass, client, DEFAULT_SCAN_INTERVAL)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: StirlingPdfConfigEntry
) -> bool:
    """Unload a config entry while leaving service actions registered."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _get_coordinator(hass: HomeAssistant) -> StirlingPdfCoordinator:
    """Return the coordinator for the single supported config entry."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_configured",
        )

    entry = entries[0]
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_loaded",
        )
    return cast(StirlingPdfConfigEntry, entry).runtime_data


def _validate_path(
    hass: HomeAssistant,
    path_value: str,
    expected_suffix: str,
) -> Path:
    """Validate that a path is absolute, allowed, and has the right extension."""
    path = Path(path_value)
    if not path.is_absolute() or not hass.config.is_allowed_path(path_value):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="path_not_allowed",
            translation_placeholders={"path": path_value},
        )
    if path.suffix.lower() != expected_suffix:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_extension",
            translation_placeholders={
                "path": path_value,
                "extension": expected_suffix,
            },
        )
    return path


async def _async_read_pdf(hass: HomeAssistant, path_value: str) -> tuple[str, bytes]:
    """Read an allowed PDF without blocking Home Assistant's event loop."""
    path = _validate_path(hass, path_value, ".pdf")

    def _read() -> bytes:
        if not path.is_file():
            raise FileNotFoundError(path)
        return path.read_bytes()

    return path.name, await hass.async_add_executor_job(_read)


async def _async_write_result(
    hass: HomeAssistant,
    path_value: str,
    content: bytes,
    expected_suffix: str,
    overwrite: bool,
) -> None:
    """Write an allowed result atomically without blocking the event loop."""
    path = _validate_path(hass, path_value, expected_suffix)

    def _write() -> None:
        if not path.parent.is_dir():
            raise FileNotFoundError(path.parent)
        if not overwrite:
            with path.open("xb") as output_file:
                output_file.write(content)
            return

        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(file_descriptor, "wb") as output_file:
                output_file.write(content)
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)

    await hass.async_add_executor_job(_write)


def _normalize_languages(values: list[str]) -> list[str]:
    """Accept repeated, comma-separated, plus-separated, or spaced language codes."""
    languages = [
        language
        for value in values
        for language in _LANGUAGE_SPLIT_PATTERN.split(value.strip())
        if language
    ]
    if not languages or any(
        not _LANGUAGE_PATTERN.fullmatch(code) for code in languages
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_languages",
        )
    return languages


async def _async_handle_action(call: ServiceCall) -> None:
    """Handle one of the four Stirling PDF service actions."""
    coordinator = _get_coordinator(call.hass)
    overwrite = call.data[ATTR_OVERWRITE]

    try:
        if call.service == SERVICE_MERGE:
            files = [
                await _async_read_pdf(call.hass, path)
                for path in call.data[ATTR_FILE_PATHS]
            ]
            result = await coordinator.client.async_merge(files)
            output_suffix = ".pdf"
        else:
            filename, content = await _async_read_pdf(
                call.hass, call.data[ATTR_FILE_PATH]
            )
            if call.service == SERVICE_SPLIT:
                result = await coordinator.client.async_split(
                    filename,
                    content,
                    call.data[ATTR_PAGE_NUMBERS],
                )
                output_suffix = ".zip"
            elif call.service == SERVICE_OCR:
                result = await coordinator.client.async_ocr(
                    filename,
                    content,
                    _normalize_languages(call.data[ATTR_LANGUAGES]),
                )
                output_suffix = ".pdf"
            else:
                result = await coordinator.client.async_compress(
                    filename,
                    content,
                    call.data[ATTR_OPTIMIZE_LEVEL],
                )
                output_suffix = ".pdf"

        await _async_write_result(
            call.hass,
            call.data[ATTR_OUTPUT_PATH],
            result,
            output_suffix,
            overwrite,
        )
    except ServiceValidationError:
        raise
    except FileExistsError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="output_exists",
            translation_placeholders={"path": call.data[ATTR_OUTPUT_PATH]},
        ) from err
    except StirlingPdfAuthError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="authentication_failed",
        ) from err
    except StirlingPdfApiError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="processing_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    except OSError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="file_error",
            translation_placeholders={"error": str(err)},
        ) from err

    coordinator.record_operation(call.service)
