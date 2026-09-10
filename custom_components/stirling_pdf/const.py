"""Constants for the Stirling PDF integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "stirling_pdf"

DEFAULT_URL = "http://localhost:8080"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
DEFAULT_STATUS_TIMEOUT = 10
DEFAULT_OPERATION_TIMEOUT = 600

ATTR_FILE_PATH = "file_path"
ATTR_FILE_PATHS = "file_paths"
ATTR_OUTPUT_PATH = "output_path"
ATTR_LANGUAGES = "languages"
ATTR_OPTIMIZE_LEVEL = "optimize_level"
ATTR_PAGE_NUMBERS = "page_numbers"
ATTR_OVERWRITE = "overwrite"

SERVICE_MERGE = "merge"
SERVICE_SPLIT = "split"
SERVICE_OCR = "ocr"
SERVICE_COMPRESS = "compress"
SERVICES = (SERVICE_MERGE, SERVICE_SPLIT, SERVICE_OCR, SERVICE_COMPRESS)

ENDPOINT_STATUS = "/api/v1/info/status"
ENDPOINT_MERGE = "/api/v1/general/merge-pdfs"
ENDPOINT_SPLIT = "/api/v1/general/split-pages"
ENDPOINT_OCR = "/api/v1/misc/ocr-pdf"
ENDPOINT_COMPRESS = "/api/v1/misc/compress-pdf"

HEADER_API_KEY = "X-API-KEY"

DEFAULT_OCR_LANGUAGES = ["eng"]
DEFAULT_OCR_TYPE = "skip-text"
DEFAULT_OCR_RENDER_TYPE = "hocr"
