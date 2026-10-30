"""Exercise Basic authentication and redirect safety over real local HTTP."""

from __future__ import annotations

from base64 import b64encode

import aiohttp
import pytest
from aiohttp import web

from custom_components.stirling_pdf.api import (
    StirlingPdfApiClient,
    StirlingPdfApiError,
    StirlingPdfAuthError,
)

pytestmark = pytest.mark.usefixtures("socket_enabled")


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


@pytest.mark.parametrize("route", ["status", "health", "compress", "extract_pages"])
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
            else:
                await client.async_compress("a.pdf", b"%PDF-private-document", 5)
    assert redirected_requests == []
