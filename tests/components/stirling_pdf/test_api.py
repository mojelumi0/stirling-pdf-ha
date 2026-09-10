"""Standalone unit tests for the Stirling PDF API client."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

_API_PATH = (
    Path(__file__).resolve().parents[3]
    / "custom_components"
    / "stirling_pdf"
    / "api.py"
)
_CONST_PATH = _API_PATH.parent / "const.py"

_package_root = importlib.util.module_from_spec(
    importlib.util.spec_from_loader("custom_components", loader=None, is_package=True)
)
_component_package = importlib.util.module_from_spec(
    importlib.util.spec_from_loader(
        "custom_components.stirling_pdf", loader=None, is_package=True
    )
)
sys.modules["custom_components"] = _package_root
sys.modules["custom_components.stirling_pdf"] = _component_package

_const_spec = importlib.util.spec_from_file_location(
    "custom_components.stirling_pdf.const", _CONST_PATH
)
assert _const_spec and _const_spec.loader
_const_module = importlib.util.module_from_spec(_const_spec)
sys.modules["custom_components.stirling_pdf.const"] = _const_module
_const_spec.loader.exec_module(_const_module)

_api_spec = importlib.util.spec_from_file_location(
    "custom_components.stirling_pdf.api", _API_PATH
)
assert _api_spec and _api_spec.loader
_api_module = importlib.util.module_from_spec(_api_spec)
sys.modules["custom_components.stirling_pdf.api"] = _api_module
_api_spec.loader.exec_module(_api_module)

StirlingPdfApiClient = _api_module.StirlingPdfApiClient
StirlingPdfApiError = _api_module.StirlingPdfApiError
StirlingPdfAuthError = _api_module.StirlingPdfAuthError
StirlingPdfConnectionError = _api_module.StirlingPdfConnectionError
StirlingPdfInvalidUrlError = _api_module.StirlingPdfInvalidUrlError
normalize_base_url = _api_module.normalize_base_url


def _mock_response(
    status: int,
    *,
    json_data: object | None = None,
    text_data: str | None = None,
    read_data: bytes = b"",
) -> MagicMock:
    """Build a response usable as an asynchronous context manager."""
    if text_data is None:
        text_data = json.dumps(json_data) if json_data is not None else ""
    response = MagicMock()
    response.status = status
    response.text = AsyncMock(return_value=text_data)
    response.read = AsyncMock(return_value=read_data)

    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=response)
    context_manager.__aexit__ = AsyncMock(return_value=False)
    return context_manager


def _form_fields(session: MagicMock) -> list[tuple[str, object]]:
    """Return submitted multipart fields as name/value pairs."""
    form = session.post.call_args.kwargs["data"]
    return [(field[0]["name"], field[2]) for field in form._fields]


@pytest.fixture
def session() -> MagicMock:
    """Return a mocked aiohttp client session."""
    return MagicMock()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("http://PDF.LOCAL:8080/", "http://pdf.local:8080"),
        (" https://pdf.local/stirling/ ", "https://pdf.local/stirling"),
    ],
)
def test_normalize_base_url(value: str, expected: str) -> None:
    assert normalize_base_url(value) == expected


@pytest.mark.parametrize(
    "value",
    ["pdf.local:8080", "ftp://pdf.local", "http://user:pass@pdf.local", ""],
)
def test_normalize_base_url_rejects_invalid_values(value: str) -> None:
    with pytest.raises(StirlingPdfInvalidUrlError):
        normalize_base_url(value)


@pytest.mark.asyncio
async def test_get_status_success(session: MagicMock) -> None:
    session.get.return_value = _mock_response(
        200, json_data={"status": "UP", "version": "1.2.3"}
    )
    client = StirlingPdfApiClient(session, "http://127.0.0.1:8080")

    result = await client.async_get_status()

    assert result == {"status": "UP", "version": "1.2.3"}
    assert session.get.call_args.args[0] == "http://127.0.0.1:8080/api/v1/info/status"


@pytest.mark.asyncio
async def test_get_status_accepts_legacy_plain_text(session: MagicMock) -> None:
    session.get.return_value = _mock_response(200, text_data="UP")
    client = StirlingPdfApiClient(session, "http://127.0.0.1:8080")

    assert await client.async_get_status() == {"status": "UP"}


@pytest.mark.asyncio
async def test_get_status_rejects_html_login_page(session: MagicMock) -> None:
    session.get.return_value = _mock_response(
        200, text_data="<html><title>Login</title></html>"
    )
    client = StirlingPdfApiClient(session, "http://127.0.0.1:8080")

    with pytest.raises(StirlingPdfApiError, match="invalid non-JSON"):
        await client.async_get_status()


@pytest.mark.asyncio
async def test_get_status_sends_api_key_without_logging_it(session: MagicMock) -> None:
    session.get.return_value = _mock_response(200, json_data={"status": "UP"})
    client = StirlingPdfApiClient(session, "http://127.0.0.1:8080", api_key="secret")

    await client.async_get_status()

    assert session.get.call_args.kwargs["headers"]["X-API-KEY"] == "secret"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403])
async def test_get_status_invalid_auth_raises(session: MagicMock, status: int) -> None:
    session.get.return_value = _mock_response(status)
    client = StirlingPdfApiClient(session, "http://127.0.0.1:8080")

    with pytest.raises(StirlingPdfAuthError):
        await client.async_get_status()


@pytest.mark.asyncio
async def test_get_status_connection_error_is_wrapped(session: MagicMock) -> None:
    session.get.side_effect = aiohttp.ClientConnectionError("boom")
    client = StirlingPdfApiClient(session, "http://127.0.0.1:8080")

    with pytest.raises(StirlingPdfConnectionError):
        await client.async_get_status()


@pytest.mark.asyncio
async def test_merge_posts_files_and_required_defaults(session: MagicMock) -> None:
    session.post.return_value = _mock_response(200, read_data=b"%PDF-merged")
    client = StirlingPdfApiClient(session, "http://127.0.0.1:8080")

    result = await client.async_merge([("a.pdf", b"a"), ("b.pdf", b"b")])

    assert result == b"%PDF-merged"
    assert session.post.call_args.args[0].endswith("/api/v1/general/merge-pdfs")
    fields = _form_fields(session)
    assert [value for name, value in fields if name == "fileInput"] == [b"a", b"b"]
    assert ("sortType", "orderProvided") in fields
    assert ("removeCertSign", "false") in fields


@pytest.mark.asyncio
async def test_merge_requires_two_files(session: MagicMock) -> None:
    client = StirlingPdfApiClient(session, "http://127.0.0.1:8080")
    with pytest.raises(StirlingPdfApiError):
        await client.async_merge([("one.pdf", b"one")])
    session.post.assert_not_called()


@pytest.mark.asyncio
async def test_split_posts_page_numbers(session: MagicMock) -> None:
    session.post.return_value = _mock_response(200, read_data=b"PK\x03\x04zip")
    client = StirlingPdfApiClient(session, "http://127.0.0.1:8080")

    assert await client.async_split("input.pdf", b"pdf", "2,5") == b"PK\x03\x04zip"
    assert session.post.call_args.args[0].endswith("/api/v1/general/split-pages")
    assert ("pageNumbers", "2,5") in _form_fields(session)


@pytest.mark.asyncio
async def test_ocr_repeats_language_fields_and_sends_defaults(
    session: MagicMock,
) -> None:
    session.post.return_value = _mock_response(200, read_data=b"%PDF-ocr")
    client = StirlingPdfApiClient(session, "http://127.0.0.1:8080")

    assert await client.async_ocr("scan.pdf", b"pdf", ["eng", "deu"]) == b"%PDF-ocr"
    assert session.post.call_args.args[0].endswith("/api/v1/misc/ocr-pdf")
    fields = _form_fields(session)
    assert [value for name, value in fields if name == "languages"] == ["eng", "deu"]
    assert ("ocrType", "skip-text") in fields
    assert ("ocrRenderType", "hocr") in fields
    assert ("sidecar", "false") in fields


@pytest.mark.asyncio
async def test_compress_posts_level_and_boolean_defaults(session: MagicMock) -> None:
    session.post.return_value = _mock_response(200, read_data=b"%PDF-compressed")
    client = StirlingPdfApiClient(session, "http://127.0.0.1:8080")

    assert await client.async_compress("large.pdf", b"pdf", 5) == b"%PDF-compressed"
    assert session.post.call_args.args[0].endswith("/api/v1/misc/compress-pdf")
    fields = _form_fields(session)
    assert ("optimizeLevel", "5") in fields
    assert ("grayscale", "false") in fields


@pytest.mark.asyncio
async def test_compress_rejects_invalid_level(session: MagicMock) -> None:
    client = StirlingPdfApiClient(session, "http://127.0.0.1:8080")
    with pytest.raises(StirlingPdfApiError):
        await client.async_compress("large.pdf", b"pdf", 10)
    session.post.assert_not_called()


@pytest.mark.asyncio
async def test_post_error_includes_bounded_response_body(session: MagicMock) -> None:
    session.post.return_value = _mock_response(
        400, text_data="invalid parameters " + ("x" * 1000)
    )
    client = StirlingPdfApiClient(session, "http://127.0.0.1:8080")

    with pytest.raises(StirlingPdfApiError, match="invalid parameters") as error:
        await client.async_compress("large.pdf", b"pdf", 5)

    assert len(str(error.value)) < 700


@pytest.mark.asyncio
async def test_successful_html_response_is_not_written_as_pdf(
    session: MagicMock,
) -> None:
    session.post.return_value = _mock_response(200, read_data=b"<html>Login</html>")
    client = StirlingPdfApiClient(session, "http://127.0.0.1:8080")

    with pytest.raises(StirlingPdfApiError, match="not a PDF"):
        await client.async_compress("large.pdf", b"pdf", 5)
