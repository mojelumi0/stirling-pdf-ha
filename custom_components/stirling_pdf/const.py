"""Constants for the Stirling PDF integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "stirling_pdf"

API_KEY_PLACEHOLDER = "********"
PASSWORD_PLACEHOLDER = "********"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"
CONF_SERVER_NAME = "server_name"
CONF_SENSITIVE_ACTIONS = "enable_sensitive_actions"
CONF_EXTERNAL_ACTIONS = "enable_external_actions"
CONF_AI_ACTIONS = "enable_ai_actions"
CONF_ALLOWED_URL_HOSTS = "allowed_url_hosts"

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
ATTR_INPUT_COUNT = "input_count"
ATTR_OPERATION = "operation"
ATTR_OUTPUT_SIZE = "output_size"

SERVICE_MERGE = "merge"
SERVICE_SPLIT = "split"
SERVICE_OCR = "ocr"
SERVICE_COMPRESS = "compress"
SERVICE_EXTRACT_PAGES = "extract_pages"
SERVICES = (
    SERVICE_MERGE,
    SERVICE_SPLIT,
    SERVICE_OCR,
    SERVICE_COMPRESS,
    SERVICE_EXTRACT_PAGES,
    "rotate",
    "auto_rotate",
    "remove_pages",
    "crop",
    "scale_pages",
    "remove_blanks",
    "repair",
    "split_by_size",
    "split_by_chapters",
    "auto_split",
    "split_by_sections",
    "poster",
    "booklet",
    "multi_page_layout",
    "single_page",
    "overlay",
    "page_numbers",
    "watermark",
    "stamp",
    "add_image",
    "add_comments",
    "replace_text",
    "metadata",
    "bookmarks",
    "edit_bookmarks",
    "remove_images",
    "invert_colors",
    "scanner_effect",
    "decompress",
    "auto_rename",
    "extract_images",
    "extract_scans",
    "list_attachments",
    "extract_attachments",
    "add_attachments",
    "delete_attachment",
    "rename_attachment",
    "batch_process_attachments",
    "create_portfolio",
    "flatten_portfolio",
    "flatten",
    "unlock_pdf_forms",
    "images_to_pdf",
    "pdf_to_img",
    "pdf_to_pdfa",
    "pdf_to_text",
    "pdf_to_word",
    "file_to_pdf",
    "pdf_to_presentation",
    "pdf_to_csv",
    "pdf_to_xlsx",
    "pdf_to_xml",
    "html_to_pdf",
    "markdown_to_pdf",
    "pdf_to_html",
    "pdf_to_markdown",
    "eml_to_pdf",
    "svg_to_pdf",
    "ebook_to_pdf",
    "pdf_to_epub",
    "cbr_to_pdf",
    "cbz_to_pdf",
    "pdf_to_cbr",
    "pdf_to_cbz",
    "pdf_to_vector",
    "vector_to_pdf",
    "pdf_to_ua",
    "url_to_pdf",
    "analyze_basic_info",
    "analyze_page_count",
    "analyze_page_dimensions",
    "analyze_document_properties",
    "analyze_font_info",
    "analyze_annotation_info",
    "analyze_form_fields",
    "analyze_security_info",
    "pdf_info",
    "check_contains_text",
    "check_contains_image",
    "check_page_count",
    "check_page_size",
    "check_file_size",
    "check_page_rotation",
    "form_fields",
    "form_fields_with_coordinates",
    "form_fill",
    "form_extract_csv",
    "form_extract_xlsx",
    "form_add_fields",
    "form_modify_fields",
    "form_edit_fields",
    "form_delete_fields",
    "form_detect",
    "add_password",
    "remove_password",
    "auto_redact",
    "redact",
    "redact_execute",
    "cert_sign",
    "timestamp",
    "remove_cert_sign",
    "sanitize",
    "validate_signature",
    "verify",
    "validate_compliance",
    "accessibility_report",
    "show_javascript",
    "classify_and_label",
    "math_auditor_agent",
    "pdf_comment_agent",
)

ENDPOINT_STATUS = "/api/v1/info/status"
ENDPOINT_HEALTH = "/api/v1/info/health"
ENDPOINT_MERGE = "/api/v1/general/merge-pdfs"
ENDPOINT_SPLIT = "/api/v1/general/split-pages"
ENDPOINT_OCR = "/api/v1/misc/ocr-pdf"
ENDPOINT_COMPRESS = "/api/v1/misc/compress-pdf"
ENDPOINT_EXTRACT_PAGES = "/api/v1/general/rearrange-pages"

HEADER_API_KEY = "X-API-KEY"

DEFAULT_OCR_LANGUAGES = ["eng"]
DEFAULT_OCR_TYPE = "skip-text"
DEFAULT_OCR_RENDER_TYPE = "hocr"
