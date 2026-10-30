"""Standalone unit tests for the Stirling PDF API client."""

from __future__ import annotations

import importlib.util
import json
import sys
from base64 import b64decode
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

_TEST_PACKAGE = "_stirling_pdf_standalone"
_component_package = importlib.util.module_from_spec(
    importlib.util.spec_from_loader(_TEST_PACKAGE, loader=None, is_package=True)
)
sys.modules[_TEST_PACKAGE] = _component_package

_const_spec = importlib.util.spec_from_file_location(
    f"{_TEST_PACKAGE}.const", _CONST_PATH
)
assert _const_spec and _const_spec.loader
_const_module = importlib.util.module_from_spec(_const_spec)
sys.modules[f"{_TEST_PACKAGE}.const"] = _const_module
_const_spec.loader.exec_module(_const_module)

_api_spec = importlib.util.spec_from_file_location(f"{_TEST_PACKAGE}.api", _API_PATH)
assert _api_spec and _api_spec.loader
_api_module = importlib.util.module_from_spec(_api_spec)
sys.modules[f"{_TEST_PACKAGE}.api"] = _api_module
_api_spec.loader.exec_module(_api_module)

StirlingPdfApiClient = _api_module.StirlingPdfApiClient
StirlingPdfApiError = _api_module.StirlingPdfApiError
StirlingPdfAuthError = _api_module.StirlingPdfAuthError
StirlingPdfConnectionError = _api_module.StirlingPdfConnectionError
StirlingPdfInvalidUrlError = _api_module.StirlingPdfInvalidUrlError
StirlingPdfInvalidBasicAuthError = _api_module.StirlingPdfInvalidBasicAuthError
StirlingPdfStatusEndpointDisabledError = (
    _api_module.StirlingPdfStatusEndpointDisabledError
)
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
    [
        "pdf.local:8080",
        "ftp://pdf.local",
        "http://user:pass@pdf.local",
        "http://[invalid-ipv6",
        "http://pdf.local?token=secret",
        "http://pdf.local#fragment",
        "",
    ],
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
async def test_get_status_rejects_disabled_endpoint(session: MagicMock) -> None:
    session.get.return_value = _mock_response(
        200, text_data="This endpoint is disabled."
    )
    client = StirlingPdfApiClient(session, "http://127.0.0.1:8080")

    with pytest.raises(StirlingPdfStatusEndpointDisabledError):
        await client.async_get_status()


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
async def test_connection_checks_protected_health_without_upload(
    session: MagicMock,
) -> None:
    """A public status response must be followed by the protected check."""
    session.get.side_effect = [
        _mock_response(200, json_data={"status": "UP", "version": "3.2.0"}),
        _mock_response(200, json_data={"status": "UP", "version": "3.2.0"}),
    ]
    client = StirlingPdfApiClient(session, "https://pdf.local/stirling", "secret")

    assert await client.async_validate_connection() == {
        "status": "UP",
        "version": "3.2.0",
    }
    assert client.authentication_check_supported is True
    request = session.get.call_args
    assert request.args[0] == "https://pdf.local/stirling/api/v1/info/health"
    assert request.kwargs["headers"]["X-API-KEY"] == "secret"
    assert request.kwargs["allow_redirects"] is False
    session.post.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403])
async def test_public_status_does_not_hide_authentication_failure(
    session: MagicMock, status: int
) -> None:
    session.get.side_effect = [
        _mock_response(200, json_data={"status": "UP"}),
        _mock_response(status),
    ]
    client = StirlingPdfApiClient(session, "http://pdf.local")

    with pytest.raises(StirlingPdfAuthError):
        await client.async_validate_connection()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [404, 405, 501])
async def test_unavailable_health_keeps_legacy_status_support(
    session: MagicMock, status: int
) -> None:
    session.get.side_effect = [
        _mock_response(200, json_data={"status": "UP"}),
        _mock_response(status),
    ]
    client = StirlingPdfApiClient(session, "http://pdf.local")

    assert await client.async_validate_connection() == {"status": "UP"}
    assert client.authentication_check_supported is False


@pytest.mark.asyncio
@pytest.mark.parametrize("body", ["<html>Login</html>", "[]", '{"status": "DOWN"}'])
async def test_invalid_health_response_does_not_validate_credentials(
    session: MagicMock, body: str
) -> None:
    session.get.return_value = _mock_response(200, text_data=body)
    client = StirlingPdfApiClient(session, "http://pdf.local")

    with pytest.raises(StirlingPdfApiError):
        await client.async_check_authentication()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [302, 500])
async def test_health_redirect_and_server_error_are_not_ignored(
    session: MagicMock, status: int
) -> None:
    session.get.return_value = _mock_response(status)
    client = StirlingPdfApiClient(session, "http://pdf.local")

    with pytest.raises(StirlingPdfApiError):
        await client.async_check_authentication()


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [TimeoutError(), aiohttp.ClientConnectionError()])
async def test_health_network_failure_is_wrapped(
    session: MagicMock, error: Exception
) -> None:
    session.get.side_effect = error
    client = StirlingPdfApiClient(session, "http://pdf.local")

    with pytest.raises(StirlingPdfConnectionError):
        await client.async_check_authentication()


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
async def test_post_error_excludes_untrusted_response_body(session: MagicMock) -> None:
    """A server may echo secrets; do not propagate its response body into logs."""
    session.post.return_value = _mock_response(
        400, text_data="echoed-password echoed-api-key " + ("x" * 1000)
    )
    client = StirlingPdfApiClient(session, "http://127.0.0.1:8080")

    with pytest.raises(StirlingPdfApiError, match="HTTP 400") as error:
        await client.async_compress("large.pdf", b"pdf", 5)

    assert len(str(error.value)) < 700
    assert "echoed-password" not in str(error.value)
    assert "echoed-api-key" not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("api_key", [None, "combined-api-key"])
async def test_basic_auth_is_sent_to_status_health_and_processing(
    session: MagicMock, api_key: str | None
) -> None:
    """Use UTF-8 credentials on every route, optionally with an API key."""
    session.get.return_value = _mock_response(200, json_data={"status": "UP"})
    session.post.return_value = _mock_response(200, read_data=b"%PDF-result")
    client = StirlingPdfApiClient(
        session,
        "https://pdf.local/stirling",
        api_key,
        username="test-üser",
        password=" secret:pässword ",
    )
    await client.async_validate_connection()
    await client.async_compress("input.pdf", b"pdf", 5)
    assert client.base_url == "https://pdf.local/stirling"
    assert session.get.call_count == 2
    for request in [*session.get.call_args_list, session.post.call_args]:
        headers = request.kwargs["headers"]
        scheme, encoded = headers["Authorization"].split(" ", 1)
        assert scheme == "Basic"
        assert b64decode(encoded).decode("utf-8") == "test-üser: secret:pässword "
        assert headers.get("X-API-KEY") == api_key
        assert request.kwargs["allow_redirects"] is False
    assert "test-üser" not in repr(client)
    assert "pässword" not in repr(client)


@pytest.mark.asyncio
async def test_no_basic_authorization_header_without_credentials(
    session: MagicMock,
) -> None:
    """Existing key-only and unauthenticated deployments remain supported."""
    session.get.return_value = _mock_response(200, json_data={"status": "UP"})
    client = StirlingPdfApiClient(session, "http://pdf.local", "existing-key")
    await client.async_validate_connection()
    for request in session.get.call_args_list:
        assert "Authorization" not in request.kwargs["headers"]
        assert request.kwargs["headers"]["X-API-KEY"] == "existing-key"


@pytest.mark.parametrize(
    ("username", "password"),
    [("user", None), (None, "password"), ("user", ""), ("bad:user", "password")],
)
def test_invalid_basic_credentials_fail_before_network_access(
    session: MagicMock, username: str | None, password: str | None
) -> None:
    with pytest.raises(StirlingPdfInvalidBasicAuthError):
        StirlingPdfApiClient(
            session, "http://pdf.local", username=username, password=password
        )
    session.get.assert_not_called()
    session.post.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["status", "health", "compress"])
@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
async def test_authenticated_requests_never_follow_redirects(
    session: MagicMock, route: str, status: int
) -> None:
    session.get.return_value = _mock_response(status, text_data="echoed-secret")
    session.post.return_value = _mock_response(status, text_data="echoed-secret")
    client = StirlingPdfApiClient(
        session, "http://pdf.local", "api-secret", username="user", password="secret"
    )
    with pytest.raises(StirlingPdfApiError, match=f"HTTP {status}") as error:
        if route == "status":
            await client.async_get_status()
        elif route == "health":
            await client.async_check_authentication()
        else:
            await client.async_compress("input.pdf", b"pdf", 5)
    request = session.post.call_args if route == "compress" else session.get.call_args
    assert request.kwargs["allow_redirects"] is False
    assert "echoed-secret" not in str(error.value)


@pytest.mark.asyncio
async def test_successful_html_response_is_not_written_as_pdf(
    session: MagicMock,
) -> None:
    session.post.return_value = _mock_response(200, read_data=b"<html>Login</html>")
    client = StirlingPdfApiClient(session, "http://127.0.0.1:8080")

    with pytest.raises(StirlingPdfApiError, match="not a PDF"):
        await client.async_compress("large.pdf", b"pdf", 5)


@pytest.mark.asyncio
async def test_status_timeout_is_wrapped(session: MagicMock) -> None:
    """Expose network timeouts through the same typed connection error."""
    session.get.side_effect = TimeoutError()
    client = StirlingPdfApiClient(session, "http://pdf.local")
    with pytest.raises(StirlingPdfConnectionError, match="Timeout connecting"):
        await client.async_get_status()


@pytest.mark.asyncio
async def test_json_string_status_is_supported(session: MagicMock) -> None:
    """Support a legacy JSON string as well as unquoted plain text."""
    session.get.return_value = _mock_response(200, json_data="UP")
    client = StirlingPdfApiClient(session, "http://pdf.local")
    assert await client.async_get_status() == {"status": "UP"}


@pytest.mark.asyncio
@pytest.mark.parametrize("body", ["[]", "null", "true", "123"])
async def test_status_rejects_non_mapping_json(session: MagicMock, body: str) -> None:
    """Valid JSON with an invalid structure is still an API error."""
    session.get.return_value = _mock_response(200, text_data=body)
    client = StirlingPdfApiClient(session, "http://pdf.local")
    with pytest.raises(StirlingPdfApiError, match="invalid response"):
        await client.async_get_status()


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [TimeoutError(), aiohttp.ClientConnectionError()])
async def test_post_network_failure_is_wrapped(
    session: MagicMock, error: Exception
) -> None:
    """Wrap processing/upload connection failures without returning file bytes."""
    session.post.side_effect = error
    client = StirlingPdfApiClient(session, "http://pdf.local")
    with pytest.raises(StirlingPdfConnectionError):
        await client.async_compress("input.pdf", b"pdf", 5)


@pytest.mark.asyncio
async def test_ocr_requires_a_language(session: MagicMock) -> None:
    """Reject an empty language list before uploading a document."""
    client = StirlingPdfApiClient(session, "http://pdf.local")
    with pytest.raises(StirlingPdfApiError, match="at least one language"):
        await client.async_ocr("input.pdf", b"pdf", [])
    session.post.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [b"", b"%PDF-not-a-zip", b"<html>Login</html>"])
async def test_split_rejects_non_zip_output(session: MagicMock, content: bytes) -> None:
    """An HTTP success must not hide a non-archive split result."""
    session.post.return_value = _mock_response(200, read_data=content)
    client = StirlingPdfApiClient(session, "http://pdf.local")
    with pytest.raises(StirlingPdfApiError, match="not a ZIP"):
        await client.async_split("input.pdf", b"pdf", "1")
