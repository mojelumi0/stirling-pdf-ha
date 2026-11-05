"""Exercise Basic authentication and redirect safety over real local HTTP."""

from __future__ import annotations

import asyncio
from base64 import b64encode

import aiohttp
import pytest
from aiohttp import web

from custom_components.stirling_pdf.api import (
    StirlingPdfApiClient,
    StirlingPdfApiError,
    StirlingPdfAuthError,
    StirlingPdfConnectionError,
)

pytestmark = pytest.mark.usefixtures("socket_enabled")


async def test_received_pdf_upload_is_not_retried_after_response_disconnect() -> None:
    """A lost response cannot tell us that the server did not process the POST."""
    requests = []

    async def receive_then_disconnect(reader, writer):
        try:
            header = await reader.readuntil(b"\r\n\r\n")
            fields = dict(
                (key.lower(), value)
                for line in header.split(b"\r\n")[1:]
                if b":" in line
                for key, value in [line.split(b":", 1)]
            )
            length = int(fields[b"content-length"].strip())
            body = await reader.readexactly(length)
            requests.append((header.split(b"\r\n", 1)[0], body))
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(receive_then_disconnect, "127.0.0.1", 0)
    async with server:
        port = server.sockets[0].getsockname()[1]
        async with aiohttp.ClientSession() as session:
            client = StirlingPdfApiClient(session, f"http://127.0.0.1:{port}")
            with pytest.raises(
                StirlingPdfConnectionError, match="server_disconnected|connection_lost"
            ):
                await client.async_compress("test.pdf", b"%PDF-synthetic-upload", 5)
    assert len(requests) == 1
    assert requests[0][0].startswith(b"POST /api/v1/misc/compress-pdf ")
    assert b"%PDF-synthetic-upload" in requests[0][1]


@pytest.mark.parametrize("api_key", [None, "test-api-key"])
async def test_all_routes_use_basic_auth_over_http(aiohttp_server, api_key) -> None:
    """Assert credentials arrive at the server, not just in mocked kwargs."""
    authorization = "Basic " + b64encode("üser: päss:word ".encode()).decode("ascii")
    requests: list[str] = []

    async def handler(request: web.Request) -> web.Response:
        assert request.headers.get("Authorization") == authorization
        assert request.headers.get("X-API-KEY") == api_key
        requests.append(request.path)
        if request.method == "GET":
            return web.json_response({"status": "UP", "version": "test"})
        reader = await request.multipart()
        files = []
        async for part in reader:
            if part.name == "fileInput":
                files.append(bytes(await part.read()))
        assert files and all(content.startswith(b"%PDF-") for content in files)
        if request.path.endswith("split-pages"):
            return web.Response(body=b"PK\x03\x04test", content_type="application/zip")
        return web.Response(body=b"%PDF-test", content_type="application/pdf")

    app = web.Application()
    app.router.add_route("*", "/{path:.*}", handler)
    server = await aiohttp_server(app)
    async with aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar()) as session:
        client = StirlingPdfApiClient(
            session,
            str(server.make_url("/stirling")),
            api_key,
            username="üser",
            password=" päss:word ",
        )
        await client.async_validate_connection()
        await client.async_merge([("a.pdf", b"%PDF-a"), ("b.pdf", b"%PDF-b")])
        await client.async_split("a.pdf", b"%PDF-a", "1")
        await client.async_extract_pages("a.pdf", b"%PDF-a", "1")
        await client.async_ocr("a.pdf", b"%PDF-a", ["eng"])
        await client.async_compress("a.pdf", b"%PDF-a", 5)
    assert requests == [
        "/stirling/api/v1/info/status",
        "/stirling/api/v1/info/health",
        "/stirling/api/v1/general/merge-pdfs",
        "/stirling/api/v1/general/split-pages",
        "/stirling/api/v1/general/rearrange-pages",
        "/stirling/api/v1/misc/ocr-pdf",
        "/stirling/api/v1/misc/compress-pdf",
    ]


@pytest.mark.parametrize("route", ["status", "health", "compress", "extract_pages"])
@pytest.mark.parametrize("password", [None, "wrong-password"])
async def test_server_rejects_missing_or_invalid_basic_credentials(
    aiohttp_server, route, password
) -> None:
    async def reject(request: web.Request) -> web.Response:
        return web.Response(
            status=401, headers={"WWW-Authenticate": 'Basic realm="PDF test"'}
        )

    app = web.Application()
    app.router.add_route("*", "/{path:.*}", reject)
    server = await aiohttp_server(app)
    async with aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar()) as session:
        client = StirlingPdfApiClient(
            session,
            str(server.make_url("/")),
            username="test-user" if password else None,
            password=password,
        )
        with pytest.raises(StirlingPdfAuthError):
            if route == "status":
                await client.async_get_status()
            elif route == "health":
                await client.async_check_authentication()
            elif route == "extract_pages":
                await client.async_extract_pages("a.pdf", b"%PDF-a", "1")
            else:
                await client.async_compress("a.pdf", b"%PDF-a", 5)


@pytest.mark.parametrize(
    "route", ["status", "health", "compress", "extract_pages", "additional_tool"]
)
async def test_redirect_target_receives_neither_credentials_nor_documents(
    aiohttp_server, route
) -> None:
    redirected_requests: list[str] = []

    async def target(request: web.Request) -> web.Response:
        redirected_requests.append(request.path)
        return web.Response(body=b"%PDF-unexpected")

    target_app = web.Application()
    target_app.router.add_route("*", "/{path:.*}", target)
    target_server = await aiohttp_server(target_app)

    async def redirect(request: web.Request) -> web.Response:
        return web.Response(
            status=307, headers={"Location": str(target_server.make_url("/leak"))}
        )

    source_app = web.Application()
    source_app.router.add_route("*", "/{path:.*}", redirect)
    source_server = await aiohttp_server(source_app)
    async with aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar()) as session:
        client = StirlingPdfApiClient(
            session,
            str(source_server.make_url("/")),
            "test-key",
            username="test-user",
            password="test-password",
        )
        with pytest.raises(StirlingPdfApiError, match="HTTP 307"):
            if route == "status":
                await client.async_get_status()
            elif route == "health":
                await client.async_check_authentication()
            elif route == "extract_pages":
                await client.async_extract_pages("a.pdf", b"%PDF-private-document", "1")
            elif route == "additional_tool":
                await client.async_process(
                    "/api/v1/form/fill",
                    [("a.pdf", b"%PDF-private-document")],
                    {},
                    file_field="file",
                )
            else:
                await client.async_compress("a.pdf", b"%PDF-private-document", 5)
    assert redirected_requests == []


async def test_named_upload_parts_and_file_free_tools_use_real_multipart(
    aiohttp_server,
) -> None:
    """Do not mistake an urlencoded request for a multipart-only tool contract."""
    captured = []

    async def handler(request: web.Request) -> web.Response:
        assert request.headers["X-API-KEY"] == "test-key"
        assert request.headers["Authorization"].startswith("Basic ")
        reader = await request.multipart()
        fields = []
        async for part in reader:
            fields.append((part.name, part.filename, bytes(await part.read())))
        captured.append(fields)
        return web.Response(body=b"%PDF-result")

    app = web.Application()
    app.router.add_post("/{path:.*}", handler)
    server = await aiohttp_server(app)
    async with aiohttp.ClientSession() as session:
        client = StirlingPdfApiClient(
            session,
            str(server.make_url("/")),
            "test-key",
            username="user",
            password="password",
        )
        assert await client.async_process(
            "/api/v1/form/fill",
            [("a.pdf", b"%PDF-input")],
            {"data": '{"field":"value"}'},
            [("imageFile", "image.png", b"png")],
            "file",
        ) == (200, b"%PDF-result")
        await client.async_process(
            "/api/v1/convert/url/pdf", [], {"urlInput": "https://example.org"}
        )
    assert captured[0] == [
        ("file", "a.pdf", b"%PDF-input"),
        ("imageFile", "image.png", b"png"),
        ("data", None, b'{"field":"value"}'),
    ]
    assert captured[1] == [("urlInput", None, b"https://example.org")]
