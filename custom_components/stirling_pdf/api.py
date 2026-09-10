"""Asynchronous client for the Stirling PDF API."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

import aiohttp
from yarl import URL

from .const import (
    DEFAULT_OCR_RENDER_TYPE,
    DEFAULT_OCR_TYPE,
    DEFAULT_OPERATION_TIMEOUT,
    DEFAULT_STATUS_TIMEOUT,
    ENDPOINT_COMPRESS,
    ENDPOINT_MERGE,
    ENDPOINT_OCR,
    ENDPOINT_SPLIT,
    ENDPOINT_STATUS,
    HEADER_API_KEY,
)

type FormValue = str | int | bool | Sequence[str]


class StirlingPdfApiError(Exception):
    """Base error raised by the Stirling PDF API client."""


class StirlingPdfAuthError(StirlingPdfApiError):
    """Raised when an API key is missing or rejected."""


class StirlingPdfConnectionError(StirlingPdfApiError):
    """Raised when the Stirling PDF instance cannot be reached."""


class StirlingPdfInvalidUrlError(StirlingPdfApiError):
    """Raised when a base URL is invalid."""


def normalize_base_url(value: str) -> str:
    """Validate and normalize a Stirling PDF base URL."""
    try:
        url = URL(value.strip())
    except ValueError as err:
        raise StirlingPdfInvalidUrlError("Invalid URL") from err

    if (
        url.scheme not in {"http", "https"}
        or url.host is None
        or url.user is not None
        or url.password is not None
        or url.query_string
        or url.fragment
    ):
        raise StirlingPdfInvalidUrlError("URL must be an HTTP(S) base URL")

    normalized_path = url.path.rstrip("/")
    return str(url.with_path(normalized_path))


class StirlingPdfApiClient:
    """Thin asynchronous wrapper around the Stirling PDF REST API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        api_key: str | None = None,
        *,
        status_timeout: int = DEFAULT_STATUS_TIMEOUT,
        operation_timeout: int = DEFAULT_OPERATION_TIMEOUT,
    ) -> None:
        """Initialize the client with a shared aiohttp session."""
        self._session = session
        self._base_url = normalize_base_url(base_url)
        self._api_key = api_key or None
        self._status_timeout = aiohttp.ClientTimeout(total=status_timeout)
        self._operation_timeout = aiohttp.ClientTimeout(total=operation_timeout)

    @property
    def base_url(self) -> str:
        """Return the normalized configured base URL."""
        return self._base_url

    def _headers(self) -> dict[str, str]:
        """Return request headers without logging sensitive values."""
        headers = {"Accept": "application/json, application/pdf, application/zip"}
        if self._api_key:
            headers[HEADER_API_KEY] = self._api_key
        return headers

    async def async_get_status(self) -> dict[str, Any]:
        """Return status and version information from the instance."""
        url = f"{self._base_url}{ENDPOINT_STATUS}"
        try:
            async with self._session.get(
                url, headers=self._headers(), timeout=self._status_timeout
            ) as response:
                await self._raise_for_status(response, url)
                body = await response.text()
        except TimeoutError as err:
            raise StirlingPdfConnectionError(f"Timeout connecting to {url}") from err
        except aiohttp.ClientError as err:
            raise StirlingPdfConnectionError(f"Cannot connect to {url}") from err

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            status = body.strip()
            if status and len(status) <= 100 and "<" not in status:
                return {"status": status}
            raise StirlingPdfApiError(
                "The status endpoint returned an invalid non-JSON response"
            )

        if isinstance(data, str):
            return {"status": data}
        if not isinstance(data, dict):
            raise StirlingPdfApiError(
                "The status endpoint returned an invalid response"
            )
        return data

    async def _async_post_files(
        self,
        endpoint: str,
        files: Sequence[tuple[str, bytes]],
        data: Mapping[str, FormValue] | None = None,
    ) -> bytes:
        """POST PDF files and form fields, then return the raw response body."""
        url = f"{self._base_url}{endpoint}"
        form = aiohttp.FormData()
        for filename, content in files:
            form.add_field(
                "fileInput",
                content,
                filename=filename,
                content_type="application/pdf",
            )
        for key, value in (data or {}).items():
            values = (
                value
                if isinstance(value, Sequence) and not isinstance(value, str)
                else [value]
            )
            for item in values:
                if isinstance(item, bool):
                    serialized = str(item).lower()
                else:
                    serialized = str(item)
                form.add_field(key, serialized)

        try:
            async with self._session.post(
                url,
                data=form,
                headers=self._headers(),
                timeout=self._operation_timeout,
            ) as response:
                await self._raise_for_status(response, endpoint)
                return await response.read()
        except TimeoutError as err:
            raise StirlingPdfConnectionError(f"Timeout calling {url}") from err
        except aiohttp.ClientError as err:
            raise StirlingPdfConnectionError(f"Cannot connect to {url}") from err

    @staticmethod
    async def _raise_for_status(
        response: aiohttp.ClientResponse, request_name: str
    ) -> None:
        """Raise a typed error for unsuccessful HTTP responses."""
        if response.status in (401, 403):
            raise StirlingPdfAuthError("Invalid or missing API key")
        if 200 <= response.status < 300:
            return

        body = (await response.text()).strip()
        detail = body[:500] if body else "No response body"
        raise StirlingPdfApiError(
            f"Stirling PDF returned HTTP {response.status} for {request_name}: {detail}"
        )

    async def async_merge(self, files: Sequence[tuple[str, bytes]]) -> bytes:
        """Merge at least two PDFs in the supplied order."""
        if len(files) < 2:
            raise StirlingPdfApiError("Merging requires at least two files")
        result = await self._async_post_files(
            ENDPOINT_MERGE,
            files,
            data={"sortType": "orderProvided", "removeCertSign": False},
        )
        self._ensure_pdf(result)
        return result

    async def async_split(
        self, filename: str, content: bytes, page_numbers: str
    ) -> bytes:
        """Split a PDF after the supplied page numbers and return a ZIP archive."""
        result = await self._async_post_files(
            ENDPOINT_SPLIT,
            [(filename, content)],
            data={"pageNumbers": page_numbers},
        )
        self._ensure_zip(result)
        return result

    async def async_ocr(
        self, filename: str, content: bytes, languages: Sequence[str]
    ) -> bytes:
        """Run OCR on a PDF with safe, non-destructive defaults."""
        if not languages:
            raise StirlingPdfApiError("OCR requires at least one language")
        result = await self._async_post_files(
            ENDPOINT_OCR,
            [(filename, content)],
            data={
                "languages": languages,
                "sidecar": False,
                "deskew": False,
                "rotatePages": False,
                "clean": False,
                "cleanFinal": False,
                "ocrType": DEFAULT_OCR_TYPE,
                "ocrRenderType": DEFAULT_OCR_RENDER_TYPE,
                "removeImagesAfter": False,
            },
        )
        self._ensure_pdf(result)
        return result

    async def async_compress(
        self, filename: str, content: bytes, optimize_level: int
    ) -> bytes:
        """Compress a PDF with an optimization level from 1 through 9."""
        if not 1 <= optimize_level <= 9:
            raise StirlingPdfApiError("Optimization level must be between 1 and 9")
        result = await self._async_post_files(
            ENDPOINT_COMPRESS,
            [(filename, content)],
            data={
                "optimizeLevel": optimize_level,
                "linearize": False,
                "normalize": False,
                "grayscale": False,
            },
        )
        self._ensure_pdf(result)
        return result

    @staticmethod
    def _ensure_pdf(content: bytes) -> None:
        """Reject successful HTTP responses that are not PDF documents."""
        if b"%PDF-" not in content[:1024]:
            raise StirlingPdfApiError("Stirling PDF returned data that is not a PDF")

    @staticmethod
    def _ensure_zip(content: bytes) -> None:
        """Reject successful HTTP responses that are not ZIP archives."""
        if not content.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
            raise StirlingPdfApiError("Stirling PDF returned data that is not a ZIP")
