"""Opt-in API contract tests against a real, disposable Stirling PDF server."""

from __future__ import annotations

import importlib
import io
import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from types import ModuleType
from zipfile import ZipFile

import aiohttp
import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

# Load the HTTP client without executing Home Assistant's integration setup.
_PACKAGE_NAME = "_stirling_pdf_live"
_package = ModuleType(_PACKAGE_NAME)
_package.__path__ = [
    str(Path(__file__).resolve().parents[1] / "custom_components" / "stirling_pdf")
]
sys.modules[_PACKAGE_NAME] = _package
_api = importlib.import_module(f"{_PACKAGE_NAME}.api")
StirlingPdfApiClient = _api.StirlingPdfApiClient
StirlingPdfAuthError = _api.StirlingPdfAuthError


def _pdf(*markers: str) -> bytes:
    """Create identifiable pages with compressible, non-sensitive content."""
    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_reference = writer._add_object(font)
    for marker in markers:
        page = writer.add_blank_page(width=300, height=400)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_reference})}
        )
        stream = DecodedStreamObject()
        stream.set_data(
            f"BT /F1 18 Tf 30 200 Td ({marker}) Tj ET\n".encode("ascii")
            + b"% Synthetic compression-test padding: "
            + b" " * 32768
            + b"\n"
        )
        page[NameObject("/Contents")] = writer._add_object(stream)
    result = io.BytesIO()
    writer.write(result)
    return result.getvalue()


def _markers(content: bytes) -> list[str]:
    """Read every page to check content as well as the PDF signature."""
    return [
        page.extract_text().strip() for page in PdfReader(io.BytesIO(content)).pages
    ]


@pytest.fixture
def server_url() -> str:
    """Only contact a server explicitly selected for these opt-in tests."""
    url = os.environ.get("STIRLING_PDF_URL")
    if not url:
        pytest.skip("Set STIRLING_PDF_URL to a disposable test server")
    return url


@pytest.fixture
async def session() -> AsyncIterator[aiohttp.ClientSession]:
    """Avoid session cookies masking missing API-key authentication."""
    async with aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar()) as client:
        yield client


@pytest.fixture
def client(session: aiohttp.ClientSession, server_url: str):
    """Return the production HTTP client with the CI server's test key."""
    return StirlingPdfApiClient(
        session,
        server_url,
        os.environ.get("STIRLING_PDF_API_KEY"),
        operation_timeout=120,
    )


def test_generated_fixture_has_identifiable_pages() -> None:
    """Ensure a faulty fixture cannot make all server checks misleading."""
    assert _markers(_pdf("A1", "A2")) == ["A1", "A2"]


async def test_status_and_authenticated_health(client) -> None:
    status = await client.async_validate_connection()

    assert status["status"] == "UP"
    assert status["version"].removeprefix("v") == "3.2.0"
    assert client.authentication_check_supported is True


async def test_merge_preserves_requested_order_and_unicode_filenames(client) -> None:
    merged = await client.async_merge(
        [("B test.pdf", _pdf("B1")), ("A ä.pdf", _pdf("A1", "A2"))]
    )

    assert _markers(merged) == ["B1", "A1", "A2"]


async def test_split_returns_complete_pdf_segments(client) -> None:
    content = await client.async_split("three-pages.pdf", _pdf("B1", "A1", "A2"), "1")

    with ZipFile(io.BytesIO(content)) as archive:
        assert archive.testzip() is None
        names = [name for name in archive.namelist() if name.lower().endswith(".pdf")]
        assert len(names) == 2
        segments = sorted(_markers(archive.read(name)) for name in names)
    assert segments == [["A1", "A2"], ["B1"]]


async def test_compress_preserves_pages_and_text(client) -> None:
    source = _pdf("A1", "A2")
    compressed = await client.async_compress("padded.pdf", source, 5)

    assert _markers(compressed) == ["A1", "A2"]
    assert len(compressed) < len(source)


@pytest.mark.parametrize("api_key", [None, "invalid-test-key"])
async def test_missing_and_invalid_keys_follow_server_security(
    session: aiohttp.ClientSession,
    server_url: str,
    api_key: str | None,
) -> None:
    """Public status must not hide protected health or processing failures."""
    client = StirlingPdfApiClient(session, server_url, api_key, operation_timeout=120)
    assert (await client.async_get_status())["status"] == "UP"

    if os.environ.get("STIRLING_PDF_REQUIRE_AUTH", "false").lower() == "true":
        with pytest.raises(StirlingPdfAuthError):
            await client.async_validate_connection()
        with pytest.raises(StirlingPdfAuthError):
            await client.async_merge([("a.pdf", _pdf("A1")), ("b.pdf", _pdf("B1"))])
    else:
        assert (await client.async_validate_connection())["status"] == "UP"
        merged = await client.async_merge(
            [("a.pdf", _pdf("A1")), ("b.pdf", _pdf("B1"))]
        )
        assert _markers(merged) == ["A1", "B1"]
