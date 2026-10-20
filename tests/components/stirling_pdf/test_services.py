"""Tests for Stirling PDF actions through Home Assistant's service registry."""

from __future__ import annotations

from pathlib import Path
from threading import get_ident
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stirling_pdf.api import (
    StirlingPdfApiError,
    StirlingPdfAuthError,
)
from custom_components.stirling_pdf.const import (
    ATTR_FILE_PATH,
    ATTR_FILE_PATHS,
    ATTR_INPUT_COUNT,
    ATTR_LANGUAGES,
    ATTR_OPERATION,
    ATTR_OPTIMIZE_LEVEL,
    ATTR_OUTPUT_PATH,
    ATTR_OUTPUT_SIZE,
    ATTR_OVERWRITE,
    ATTR_PAGE_NUMBERS,
    DOMAIN,
    SERVICE_COMPRESS,
    SERVICE_MERGE,
    SERVICE_OCR,
    SERVICE_SPLIT,
)

PDF_INPUT = b"%PDF-1.4\ninput\n%%EOF\n"
PDF_RESULT = b"%PDF-1.4\nresult\n%%EOF\n"
ZIP_RESULT = b"PK\x03\x04archive"


def _allow_test_directory(hass: HomeAssistant, path: Path) -> None:
    """Allow service actions to access the temporary test directory."""
    hass.config.allowlist_external_dirs.add(str(path))


async def test_all_actions_write_results_and_update_statistics(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    tmp_path: Path,
) -> None:
    """Test all four actions through Home Assistant's public service interface."""
    _allow_test_directory(hass, tmp_path)
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    first.write_bytes(PDF_INPUT)
    second.write_bytes(PDF_INPUT)

    coordinator = loaded_entry.runtime_data
    client = coordinator.client
    client.async_merge = AsyncMock(return_value=PDF_RESULT)
    client.async_split = AsyncMock(return_value=ZIP_RESULT)
    client.async_ocr = AsyncMock(return_value=PDF_RESULT)
    client.async_compress = AsyncMock(return_value=PDF_RESULT)

    merged = tmp_path / "merged.pdf"
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MERGE,
        {
            ATTR_FILE_PATHS: [str(first), str(second)],
            ATTR_OUTPUT_PATH: str(merged),
        },
        blocking=True,
    )

    split = tmp_path / "split.zip"
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SPLIT,
        {
            ATTR_FILE_PATH: str(first),
            ATTR_PAGE_NUMBERS: "2,5",
            ATTR_OUTPUT_PATH: str(split),
        },
        blocking=True,
    )

    ocr = tmp_path / "ocr.pdf"
    await hass.services.async_call(
        DOMAIN,
        SERVICE_OCR,
        {
            ATTR_FILE_PATH: str(first),
            ATTR_LANGUAGES: "eng + deu",
            ATTR_OUTPUT_PATH: str(ocr),
        },
        blocking=True,
    )

    compressed = tmp_path / "compressed.pdf"
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_COMPRESS,
        {
            ATTR_FILE_PATH: str(first),
            ATTR_OPTIMIZE_LEVEL: 7,
            ATTR_OUTPUT_PATH: str(compressed),
        },
        blocking=True,
        return_response=True,
    )

    assert merged.read_bytes() == PDF_RESULT
    assert split.read_bytes() == ZIP_RESULT
    assert ocr.read_bytes() == PDF_RESULT
    assert compressed.read_bytes() == PDF_RESULT
    client.async_merge.assert_awaited_once_with(
        [("first.pdf", PDF_INPUT), ("second.pdf", PDF_INPUT)]
    )
    client.async_split.assert_awaited_once_with("first.pdf", PDF_INPUT, "2,5")
    client.async_ocr.assert_awaited_once_with("first.pdf", PDF_INPUT, ["eng", "deu"])
    client.async_compress.assert_awaited_once_with("first.pdf", PDF_INPUT, 7)
    assert response == {
        ATTR_OPERATION: SERVICE_COMPRESS,
        ATTR_OUTPUT_PATH: str(compressed),
        ATTR_OUTPUT_SIZE: len(PDF_RESULT),
        ATTR_INPUT_COUNT: 1,
    }
    assert coordinator.jobs_processed == 4
    assert coordinator.last_operation == SERVICE_COMPRESS


async def test_existing_output_requires_overwrite(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    tmp_path: Path,
) -> None:
    """Test that an existing output is protected by default."""
    _allow_test_directory(hass, tmp_path)
    source = tmp_path / "source.pdf"
    output = tmp_path / "output.pdf"
    source.write_bytes(PDF_INPUT)
    output.write_bytes(b"original")
    client_call = AsyncMock(return_value=PDF_RESULT)
    loaded_entry.runtime_data.client.async_compress = client_call

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_COMPRESS,
            {
                ATTR_FILE_PATH: str(source),
                ATTR_OUTPUT_PATH: str(output),
            },
            blocking=True,
        )

    assert output.read_bytes() == b"original"
    client_call.assert_not_awaited()
    assert loaded_entry.runtime_data.jobs_processed == 0


@pytest.mark.parametrize(
    "service", [SERVICE_MERGE, SERVICE_SPLIT, SERVICE_OCR, SERVICE_COMPRESS]
)
@pytest.mark.parametrize(
    ("failure", "expected_error"),
    [
        ("wrong_extension", ServiceValidationError),
        ("not_allowed", ServiceValidationError),
        ("missing_directory", HomeAssistantError),
        ("existing_output", ServiceValidationError),
    ],
)
async def test_invalid_output_is_rejected_before_reading_or_uploading(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    tmp_path: Path,
    service: str,
    failure: str,
    expected_error: type[HomeAssistantError],
) -> None:
    """Reject bad destinations for every action before touching the inputs."""
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    _allow_test_directory(hass, allowed)
    first = allowed / "first.pdf"
    second = allowed / "second.pdf"
    first.write_bytes(PDF_INPUT)
    second.write_bytes(PDF_INPUT)
    suffix = ".zip" if service == SERVICE_SPLIT else ".pdf"
    output = allowed / f"result{suffix}"
    if failure == "wrong_extension":
        output = allowed / ("result.pdf" if service == SERVICE_SPLIT else "result.zip")
    elif failure == "not_allowed":
        output = tmp_path / f"outside-allowlist{suffix}"
    elif failure == "missing_directory":
        output = allowed / "missing" / f"result{suffix}"
    else:
        output.write_bytes(b"original")

    coordinator = loaded_entry.runtime_data
    coordinator.record_operation(SERVICE_MERGE)
    last_operation_time = coordinator.last_operation_time
    client_call = AsyncMock()
    setattr(coordinator.client, f"async_{service}", client_call)
    data = {ATTR_OUTPUT_PATH: str(output)}
    if service == SERVICE_MERGE:
        data[ATTR_FILE_PATHS] = [str(first), str(second)]
    else:
        data[ATTR_FILE_PATH] = str(first)
        if service == SERVICE_SPLIT:
            data[ATTR_PAGE_NUMBERS] = "1"

    with (
        patch(
            "custom_components.stirling_pdf._async_read_pdf", new_callable=AsyncMock
        ) as read_pdf,
        pytest.raises(expected_error),
    ):
        await hass.services.async_call(DOMAIN, service, data, blocking=True)

    read_pdf.assert_not_awaited()
    client_call.assert_not_awaited()
    assert coordinator.jobs_processed == 1
    assert coordinator.last_operation == SERVICE_MERGE
    assert coordinator.last_operation_time == last_operation_time
    assert first.read_bytes() == second.read_bytes() == PDF_INPUT
    if failure == "existing_output":
        assert output.read_bytes() == b"original"
    else:
        assert not output.exists()


@pytest.mark.parametrize("overwrite", [False, True])
async def test_directory_destination_is_rejected_before_api_call(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    tmp_path: Path,
    overwrite: bool,
) -> None:
    """Do not process a PDF for a destination which is actually a directory."""
    _allow_test_directory(hass, tmp_path)
    source = tmp_path / "source.pdf"
    source.write_bytes(PDF_INPUT)
    output = tmp_path / "output.pdf"
    output.mkdir()
    client_call = AsyncMock(return_value=PDF_RESULT)
    loaded_entry.runtime_data.client.async_compress = client_call

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_COMPRESS,
            {
                ATTR_FILE_PATH: str(source),
                ATTR_OUTPUT_PATH: str(output),
                ATTR_OVERWRITE: overwrite,
            },
            blocking=True,
        )

    client_call.assert_not_awaited()
    assert output.is_dir()
    assert loaded_entry.runtime_data.jobs_processed == 0


@pytest.mark.parametrize(
    "change", ["file_appears", "allowlist_removed", "directory_removed"]
)
async def test_destination_is_rechecked_after_pdf_processing(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    tmp_path: Path,
    change: str,
) -> None:
    """Preserve write protection if the destination changes after preflight."""
    _allow_test_directory(hass, tmp_path)
    source = tmp_path / "source.pdf"
    source.write_bytes(PDF_INPUT)
    destination = tmp_path / "destination"
    destination.mkdir()
    output = destination / "output.pdf"

    async def process_pdf(*args: object) -> bytes:
        # The preflight must not reserve or create the output file.
        assert not output.exists()
        if change == "file_appears":
            output.write_bytes(b"created by another operation")
        elif change == "allowlist_removed":
            hass.config.allowlist_external_dirs.remove(str(tmp_path))
        else:
            destination.rmdir()
        return PDF_RESULT

    client_call = AsyncMock(side_effect=process_pdf)
    coordinator = loaded_entry.runtime_data
    coordinator.client.async_compress = client_call
    coordinator.record_operation(SERVICE_MERGE)
    last_operation_time = coordinator.last_operation_time

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_COMPRESS,
            {ATTR_FILE_PATH: str(source), ATTR_OUTPUT_PATH: str(output)},
            blocking=True,
        )

    client_call.assert_awaited_once_with("source.pdf", PDF_INPUT, 5)
    assert coordinator.jobs_processed == 1
    assert coordinator.last_operation == SERVICE_MERGE
    assert coordinator.last_operation_time == last_operation_time
    assert source.read_bytes() == PDF_INPUT
    if change == "file_appears":
        assert output.read_bytes() == b"created by another operation"
    else:
        assert not output.exists()


async def test_path_validation_runs_on_executor(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    tmp_path: Path,
) -> None:
    """Run preflight, input, and final allowlist checks off the event-loop thread."""
    _allow_test_directory(hass, tmp_path)
    source = tmp_path / "source.pdf"
    output = tmp_path / "output.pdf"
    source.write_bytes(PDF_INPUT)
    loaded_entry.runtime_data.client.async_compress = AsyncMock(return_value=PDF_RESULT)
    event_loop_thread = get_ident()
    original_check = type(hass.config).is_allowed_path
    checked_paths: list[str] = []

    def check_path(config, path_value: str) -> bool:
        assert get_ident() != event_loop_thread
        checked_paths.append(path_value)
        return original_check(config, path_value)

    with patch.object(type(hass.config), "is_allowed_path", new=check_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_COMPRESS,
            {ATTR_FILE_PATH: str(source), ATTR_OUTPUT_PATH: str(output)},
            blocking=True,
        )

    assert checked_paths == [str(output), str(source), str(output)]
    assert output.read_bytes() == PDF_RESULT
    assert loaded_entry.runtime_data.jobs_processed == 1


async def test_overwrite_replaces_existing_output(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    tmp_path: Path,
) -> None:
    """Test the explicit atomic-overwrite path."""
    _allow_test_directory(hass, tmp_path)
    source = tmp_path / "source.pdf"
    output = tmp_path / "output.pdf"
    source.write_bytes(PDF_INPUT)
    output.write_bytes(b"original")
    loaded_entry.runtime_data.client.async_compress = AsyncMock(return_value=PDF_RESULT)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_COMPRESS,
        {
            ATTR_FILE_PATH: str(source),
            ATTR_OUTPUT_PATH: str(output),
            ATTR_OVERWRITE: True,
        },
        blocking=True,
    )

    assert output.read_bytes() == PDF_RESULT
    assert loaded_entry.runtime_data.jobs_processed == 1


@pytest.mark.parametrize(
    ("filename", "languages"),
    [("source.txt", ["eng"]), ("source.pdf", ["eng", "../deu"])],
)
async def test_invalid_action_input_is_rejected_before_api_call(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    tmp_path: Path,
    filename: str,
    languages: list[str],
) -> None:
    """Test extension and OCR-language validation."""
    _allow_test_directory(hass, tmp_path)
    source = tmp_path / filename
    source.write_bytes(PDF_INPUT)
    output = tmp_path / "output.pdf"
    client_call = AsyncMock(return_value=PDF_RESULT)
    loaded_entry.runtime_data.client.async_ocr = client_call

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_OCR,
            {
                ATTR_FILE_PATH: str(source),
                ATTR_LANGUAGES: languages,
                ATTR_OUTPUT_PATH: str(output),
            },
            blocking=True,
        )

    client_call.assert_not_awaited()
    assert loaded_entry.runtime_data.jobs_processed == 0


@pytest.mark.parametrize(
    "error",
    [StirlingPdfAuthError("bad key"), StirlingPdfApiError("processing failed")],
)
async def test_api_failure_does_not_write_or_increment_counter(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    tmp_path: Path,
    error: StirlingPdfApiError,
) -> None:
    """Test action failures exposed as Home Assistant errors."""
    _allow_test_directory(hass, tmp_path)
    source = tmp_path / "source.pdf"
    output = tmp_path / "output.pdf"
    source.write_bytes(PDF_INPUT)
    loaded_entry.runtime_data.client.async_compress = AsyncMock(side_effect=error)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_COMPRESS,
            {
                ATTR_FILE_PATH: str(source),
                ATTR_OUTPUT_PATH: str(output),
            },
            blocking=True,
        )

    assert not output.exists()
    assert loaded_entry.runtime_data.jobs_processed == 0
    await hass.async_block_till_done()
    reauth_flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["handler"] == DOMAIN and flow["context"]["source"] == SOURCE_REAUTH
    ]
    assert len(reauth_flows) == (1 if isinstance(error, StirlingPdfAuthError) else 0)
