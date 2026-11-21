"""Opt-in API contract tests against a real, disposable Stirling PDF server."""

from __future__ import annotations

import importlib
import io
import json
import os
import re
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from types import ModuleType
from zipfile import ZipFile

import aiohttp
import pytest
from aiohttp import web
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
StirlingPdfApiError = _api.StirlingPdfApiError

_OCR_FIXTURE = Path(__file__).parent / "fixtures" / "ocr_scan.pdf"


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
def expected_server_version() -> str:
    """Assert the version selected by CI, not a label inferred from a response."""
    return os.environ.get("STIRLING_PDF_EXPECTED_VERSION", "3.2.0")


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


async def test_status_and_authenticated_health(client, expected_server_version) -> None:
    status = await client.async_validate_connection()

    assert status["status"] == "UP"
    assert status["version"].removeprefix("v") == expected_server_version
    assert client.authentication_check_supported is True


async def test_removed_text_editor_has_no_processing_route(
    client, expected_server_version
) -> None:
    """Check the documented removal on the pinned new server, not older servers."""
    if expected_server_version not in {"3.3.0", "3.4.0"}:
        pytest.skip("The text-editor route was removed in 3.3.0")
    with pytest.raises(StirlingPdfApiError, match="HTTP 404"):
        await client.async_process(
            "/api/v1/general/edit-text",
            [("synthetic.pdf", _pdf("OLD TEXT EDITOR"))],
            {"pageNumbers": "all", "edits": "[]"},
        )


async def test_newer_servers_reject_out_of_range_poster_multiplier(
    client, expected_server_version
) -> None:
    """The newer server must reject 11 before allocating an oversized result."""
    if expected_server_version not in {"3.3.0", "3.4.0"}:
        pytest.skip("The newer poster validation starts with 3.3.0")
    with pytest.raises(StirlingPdfApiError, match="HTTP 400"):
        await client.async_process(
            "/api/v1/general/split-for-poster-print",
            [("synthetic.pdf", _pdf("POSTER LIMIT"))],
            {"pageSize": "A4", "xFactor": 11, "yFactor": 2},
        )


async def test_explicit_legacy_markdown_conversion_produces_searchable_pdf(
    client,
) -> None:
    """Exercise explicit false on all pinned versions, without external resources."""
    status, content = await client.async_process(
        "/api/v1/convert/markdown/pdf",
        [("synthetic.md", b"# CONVERTER LEGACY 12345\n\nSynthetic local test.\n")],
        {"useStirlingOfficeConvert": False},
    )
    assert status == 200
    text = " ".join(" ".join(_markers(content)).split())
    assert "CONVERTER LEGACY 12345" in text


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


@pytest.mark.parametrize(
    ("endpoint", "fields"),
    [
        ("/api/v1/general/rotate-pdf", {"angle": 90}),
        ("/api/v1/misc/repair", {}),
        ("/api/v1/misc/flatten", {"flattenOnlyForms": True}),
        (
            "/api/v1/misc/update-metadata",
            {"deleteAll": False, "title": "Synthetic test title"},
        ),
    ],
)
async def test_representative_additional_tools_preserve_page_content(
    client, endpoint, fields
) -> None:
    """Exercise selected catalog tools on the real pinned server, not all tools."""
    status, content = await client.async_process(
        endpoint, [("a.pdf", _pdf("A1", "A2"))], fields
    )
    assert status == 200
    assert _markers(content) == ["A1", "A2"]
    reader = PdfReader(io.BytesIO(content))
    if endpoint.endswith("rotate-pdf"):
        assert all(page.rotation == 90 for page in reader.pages)
    if endpoint.endswith("update-metadata"):
        assert reader.metadata.title == "Synthetic test title"


async def test_additional_analysis_page_count(client) -> None:
    status, content = await client.async_process(
        "/api/v1/analysis/page-count", [("a.pdf", _pdf("A1", "A2"))], {}
    )
    assert status == 200
    assert json.loads(content)["pageCount"] == 2


@pytest.mark.parametrize(
    ("endpoint", "filename", "content", "fields"),
    [
        (
            "/api/v1/convert/pdf/vector",
            "synthetic.pdf",
            _pdf("VECTOR REMOVED"),
            {"outputFormat": "eps", "prepress": False},
        ),
        (
            "/api/v1/convert/vector/pdf",
            "synthetic.ps",
            b"%!PS\nshowpage\n",
            {"outputFormat": "eps", "prepress": False},
        ),
    ],
)
async def test_340_vector_routes_are_removed(
    client, expected_server_version, endpoint, filename, content, fields
) -> None:
    if expected_server_version != "3.4.0":
        pytest.skip("The vector routes were removed in 3.4.0")
    with pytest.raises(StirlingPdfApiError, match="HTTP 404"):
        await client.async_process(endpoint, [(filename, content)], fields)


def _pdf_with_metadata() -> bytes:
    writer = PdfWriter()
    writer.append_pages_from_reader(PdfReader(io.BytesIO(_pdf("METADATA CONTENT"))))
    writer.add_metadata(
        {
            "/Title": "Original title",
            "/Author": "Synthetic author",
            "/Subject": "Synthetic subject",
            "/Keywords": "Synthetic keywords",
            "/CreationDate": "D:20260102030405Z",
            "/ModDate": "D:20260203040506Z",
            "/CustomField": "Synthetic custom value",
        }
    )
    result = io.BytesIO()
    writer.write(result)
    return result.getvalue()


async def test_legacy_metadata_update_still_clears_omitted_standard_fields(
    client,
) -> None:
    """Omitting the new option must preserve the original behavior on every baseline."""
    status, content = await client.async_process(
        "/api/v1/misc/update-metadata",
        [("metadata.pdf", _pdf_with_metadata())],
        {"deleteAll": False, "title": "Replacement title"},
    )
    assert status == 200
    reader = PdfReader(io.BytesIO(content))
    assert reader.metadata.title == "Replacement title"
    assert reader.metadata.author is None
    assert reader.metadata.subject is None
    assert _markers(content) == ["METADATA CONTENT"]


@pytest.mark.parametrize("keep", [True, False])
async def test_340_metadata_option_preserves_fields_only_when_enabled(
    client, expected_server_version, keep
) -> None:
    if expected_server_version != "3.4.0":
        pytest.skip("keepOmitted was added in 3.4.0")
    status, content = await client.async_process(
        "/api/v1/misc/update-metadata",
        [("metadata.pdf", _pdf_with_metadata())],
        {"deleteAll": False, "title": "Replacement title", "keepOmitted": keep},
    )
    assert status == 200
    metadata = PdfReader(io.BytesIO(content)).metadata
    assert metadata.title == "Replacement title"
    assert metadata.author == ("Synthetic author" if keep else None)
    assert metadata.subject == ("Synthetic subject" if keep else None)
    assert metadata["/CustomField"] == "Synthetic custom value"
    if keep:
        assert metadata["/CreationDate"] == "D:20260102030405Z"
        assert metadata["/ModDate"] == "D:20260203040506Z"
    assert _markers(content) == ["METADATA CONTENT"]


async def test_340_delete_all_takes_precedence_over_metadata_preservation(
    client, expected_server_version
) -> None:
    if expected_server_version != "3.4.0":
        pytest.skip("keepOmitted was added in 3.4.0")
    status, content = await client.async_process(
        "/api/v1/misc/update-metadata",
        [("metadata.pdf", _pdf_with_metadata())],
        {"deleteAll": True, "keepOmitted": True, "title": "Must not survive"},
    )
    assert status == 200
    metadata = PdfReader(io.BytesIO(content)).metadata
    assert not metadata or not {
        "/Title",
        "/Author",
        "/Subject",
        "/CustomField",
        "/CreationDate",
        "/ModDate",
    }.intersection(metadata)
    assert _markers(content) == ["METADATA CONTENT"]


@pytest.mark.parametrize(
    ("unit", "width", "height", "points_per_unit"),
    [(None, 210, 297, 72 / 25.4), ("cm", 21, 29.7, 72 / 2.54), ("in", 8.5, 11, 72)],
)
async def test_340_custom_page_size_preserves_content_and_exact_requested_size(
    client, expected_server_version, unit, width, height, points_per_unit
) -> None:
    if expected_server_version != "3.4.0":
        pytest.skip("CUSTOM dimensions were added in 3.4.0")
    fields = {
        "pageSize": "CUSTOM",
        "customWidth": width,
        "customHeight": height,
        "orientation": "LANDSCAPE",
        "scaleFactor": 1,
    }
    if unit is not None:
        fields["customUnit"] = unit
    status, content = await client.async_process(
        "/api/v1/general/scale-pages", [("pages.pdf", _pdf("SIZE A", "SIZE B"))], fields
    )
    assert status == 200
    assert _markers(content) == ["SIZE A", "SIZE B"]
    pages = PdfReader(io.BytesIO(content)).pages
    assert len(pages) == 2
    for page in pages:
        # The supplied width/height, not LANDSCAPE, determine custom orientation.
        assert float(page.mediabox.width) == pytest.approx(
            width * points_per_unit, abs=0.002
        )
        assert float(page.mediabox.height) == pytest.approx(
            height * points_per_unit, abs=0.002
        )


@pytest.mark.parametrize(
    "fields",
    [
        {"pageSize": "CUSTOM", "customWidth": 210},
        {
            "pageSize": "CUSTOM",
            "customWidth": 201,
            "customHeight": 11,
            "customUnit": "in",
        },
    ],
)
async def test_340_server_rejects_missing_or_oversized_custom_dimensions(
    client, expected_server_version, fields
) -> None:
    if expected_server_version != "3.4.0":
        pytest.skip("CUSTOM dimensions were added in 3.4.0")
    with pytest.raises(StirlingPdfApiError, match="HTTP 400"):
        await client.async_process(
            "/api/v1/general/scale-pages", [("pages.pdf", _pdf("SIZE LIMIT"))], fields
        )


@pytest.mark.parametrize("profile", ["ua1", "ua2"])
async def test_340_accessibility_report_describes_an_untagged_document(
    client, expected_server_version, profile
) -> None:
    """Require a completed check, not HTTP 200 containing a validator failure."""
    if expected_server_version != "3.4.0":
        pytest.skip("The expanded accessibility report is checked on 3.4.0")
    status, content = await client.async_process(
        "/api/v1/security/accessibility-report",
        [("untagged.pdf", _pdf("ACCESSIBILITY CHECK"))],
        {"profile": profile},
    )
    assert status == 200
    report = json.loads(content)
    assert report.get("validationError") is None
    assert report["tagged"] is False
    assert report["passesAutomatedChecks"] is False
    assert isinstance(report["issues"], list) and report["issues"]
    assert report["checks"]["total"] > 0
    assert report["checks"]["failed"] > 0


@pytest.mark.parametrize(
    ("text", "expected_status"), [("A1", 200), ("UNIQUE_ABSENT_MARKER", 204)]
)
async def test_additional_text_filter_match_and_non_match(
    client, text, expected_status
) -> None:
    """Send the documented page selection; the server does not default null."""
    status, content = await client.async_process(
        "/api/v1/filter/filter-contains-text",
        [("a.pdf", _pdf("A1"))],
        {"text": text, "pageNumbers": "all"},
    )
    assert status == expected_status
    if expected_status == 204:
        assert content == b""
    else:
        assert _markers(content) == ["A1"]


@pytest.mark.parametrize(
    ("selection", "expected"),
    [
        ("2", ["A2"]),
        ("1,3-4", ["A1", "A3", "A4"]),
        ("4,1-2", ["A4", "A1", "A2"]),
    ],
)
async def test_extract_pages_preserves_selected_content_and_order(
    client, selection: str, expected: list[str]
) -> None:
    """Check page count, text content and requested ordering on a real server."""
    result = await client.async_extract_pages(
        "four-pages.pdf", _pdf("A1", "A2", "A3", "A4"), selection
    )
    assert _markers(result) == expected


def test_ocr_fixture_is_an_image_without_searchable_text() -> None:
    """A searchable source would let skip-text mode pass without doing OCR."""
    reader = PdfReader(_OCR_FIXTURE)
    assert len(reader.pages) == 1
    page = reader.pages[0]
    assert not (page.extract_text() or "").strip()
    image_objects = page["/Resources"]["/XObject"].get_object()
    images = [value.get_object() for value in image_objects.values()]
    assert sum(image["/Subtype"] == "/Image" for image in images) == 1
    assert any(
        image["/Subtype"] == "/Image"
        and image["/Width"] >= 2000
        and image["/Height"] >= 3000
        for image in images
    )


async def test_real_ocr_adds_searchable_text(client) -> None:
    """Require actual recognition from the committed synthetic scanned page."""
    source = _OCR_FIXTURE.read_bytes()
    assert _markers(source) == [""]
    result = await client.async_ocr("synthetic-scan.pdf", source, ["eng"])
    reader = PdfReader(io.BytesIO(result))
    assert len(reader.pages) == 1
    recognized = re.sub(
        r"[^A-Z0-9]", "", (reader.pages[0].extract_text() or "").upper()
    )
    for expected in ("STIRLING", "INVOICE", "12345"):
        assert expected in recognized
    assert _OCR_FIXTURE.read_bytes() == source


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


@pytest.fixture
async def basic_auth_proxy(server_url: str, unused_tcp_port: int) -> AsyncIterator[str]:
    """Model a Basic-protected direct API port in front of the real CI server.

    This is not the Community App or Supervisor. The synthetic proxy exercises
    multipart forwarding and combined credentials; the app needs a manual test.
    """
    authorization = aiohttp.encode_basic_auth("ci-proxy-user", "ci-proxy-password")
    async with aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar()) as upstream:

        async def proxy(request: web.Request) -> web.Response:
            if request.headers.get("Authorization") != authorization:
                return web.Response(
                    status=401,
                    headers={"WWW-Authenticate": 'Basic realm="Synthetic CI proxy"'},
                )
            headers = {
                name: request.headers[name]
                for name in ("Accept", "Content-Type", "X-API-KEY")
                if name in request.headers
            }
            async with upstream.request(
                request.method,
                f"{server_url.rstrip('/')}{request.rel_url}",
                headers=headers,
                data=await request.read(),
                allow_redirects=False,
            ) as response:
                return web.Response(
                    status=response.status,
                    body=await response.read(),
                    headers={"Content-Type": response.headers["Content-Type"]},
                )

        app = web.Application(client_max_size=10 * 1024 * 1024)
        app.router.add_route("*", "/{path:.*}", proxy)
        runner = web.AppRunner(app)
        await runner.setup()
        try:
            await web.TCPSite(runner, "127.0.0.1", unused_tcp_port).start()
            yield f"http://127.0.0.1:{unused_tcp_port}"
        finally:
            await runner.cleanup()


async def test_processing_through_a_basic_protected_proxy(
    session: aiohttp.ClientSession, basic_auth_proxy: str
) -> None:
    """Run real processing/extraction with Basic auth plus optional server auth."""
    client = StirlingPdfApiClient(
        session,
        basic_auth_proxy,
        os.environ.get("STIRLING_PDF_API_KEY"),
        username="ci-proxy-user",
        password="ci-proxy-password",
        operation_timeout=120,
    )
    assert (await client.async_validate_connection())["status"] == "UP"
    merged = await client.async_merge(
        [("b.pdf", _pdf("B1")), ("a.pdf", _pdf("A1", "A2"))]
    )
    assert _markers(merged) == ["B1", "A1", "A2"]
    split = await client.async_split("merged.pdf", merged, "1")
    with ZipFile(io.BytesIO(split)) as archive:
        assert archive.testzip() is None
        segments = sorted(
            _markers(archive.read(name))
            for name in archive.namelist()
            if name.lower().endswith(".pdf")
        )
    assert segments == [["A1", "A2"], ["B1"]]
    compressed = await client.async_compress("padded.pdf", _pdf("A1", "A2"), 5)
    assert _markers(compressed) == ["A1", "A2"]

    extracted = await client.async_extract_pages("merged.pdf", merged, "3,1")
    assert _markers(extracted) == ["A2", "B1"]


@pytest.mark.parametrize("password", [None, "incorrect-ci-password"])
async def test_proxy_rejects_missing_or_incorrect_basic_credentials(
    session: aiohttp.ClientSession, basic_auth_proxy: str, password: str | None
) -> None:
    client = StirlingPdfApiClient(
        session,
        basic_auth_proxy,
        os.environ.get("STIRLING_PDF_API_KEY"),
        username="ci-proxy-user" if password else None,
        password=password,
    )
    with pytest.raises(StirlingPdfAuthError):
        await client.async_validate_connection()
    with pytest.raises(StirlingPdfAuthError):
        await client.async_merge([("a.pdf", _pdf("A1")), ("b.pdf", _pdf("B1"))])
    with pytest.raises(StirlingPdfAuthError):
        await client.async_extract_pages("a.pdf", _pdf("A1"), "1")
