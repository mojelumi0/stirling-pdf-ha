# Additional action catalog

For merge, split, OCR, compression and page extraction, see the
[README](../README.md#available-actions). The additional actions below depend
on the server version, enabled tools, installed dependencies and permissions.

### Version-restricted contracts

`replace_text` uses the legacy `/api/v1/general/edit-text` API, removed upstream
in 3.3.0. Calls are rejected locally for that release and newer releases, before
file I/O or upload. The same registered action remains available to older
servers with a recognized stable version. This is not a replacement API for the
new upstream Text Editor.

Fourteen conversion actions expose `use_stirling_office_convert`, explicitly
false by default. Nine gained the option in 3.3.0: `pdf_to_pdfa`, `pdf_to_xml`,
`html_to_pdf`, `markdown_to_pdf`, `pdf_to_html`, `pdf_to_markdown`, `eml_to_pdf`,
`ebook_to_pdf` and `pdf_to_epub`. Enabling those nine options requires a recognized
stable server version at least 3.3.0, as well as the existing external-action
opt-in and user-admin permission. False is sent explicitly rather than inheriting
the server's converter default. PDF/X remains legacy; native HTML conversion
does not apply zoom. Installed dependencies still determine availability.

Unknown/custom/pre-release versions are rejected only when needed to establish
support for a restricted action or an enabled new option; they do not disable
unrelated actions.

Each action accepts `config_entry_id`. Binary results require `output_path` with
the listed extension; JSON and filter outputs may instead use action response data.
HA fields use `snake_case`, for example `render_dpi`, `page_numbers` and
`image_file`. The integration maps them to the original Stirling PDF multipart
names (`renderDpi`, `pageNumbers` and `imageFile`). Fields are shown individually
in the action editor; descriptions identify their underlying API names.

Additional tools accept up to 32 local files and 64 MiB total input. Structured
fields and returned JSON have a 4 MiB limit. These limits do not make downloads
streaming or cap memory used by every response.

For URL-to-PDF and timestamping, use **Allowed URL hosts** on the selected
server entry. Enter exact hostnames separated by commas. URL-to-PDF requires
HTTP(S) without embedded credentials, and timestamping requires an explicit
`tsa_url`. The host list is not a sandbox for redirects, DNS, embedded
resources or server-side backends. Review the server's own network controls.

| Action | Group | Input extensions | Output extensions | Endpoint |
|---|---|---|---|---|
| `stirling_pdf.rotate` | standard | .pdf | .pdf | `/api/v1/general/rotate-pdf` |
| `stirling_pdf.auto_rotate` | standard | .pdf | .pdf, .json | `/api/v1/misc/auto-rotate-pdf` |
| `stirling_pdf.remove_pages` | standard | .pdf | .pdf | `/api/v1/general/remove-pages` |
| `stirling_pdf.crop` | standard | .pdf | .pdf | `/api/v1/general/crop` |
| `stirling_pdf.scale_pages` | standard | .pdf | .pdf | `/api/v1/general/scale-pages` |
| `stirling_pdf.remove_blanks` | standard | .pdf | .pdf | `/api/v1/misc/remove-blanks` |
| `stirling_pdf.repair` | standard | .pdf | .pdf | `/api/v1/misc/repair` |
| `stirling_pdf.split_by_size` | standard | .pdf | .zip, .pdf, .png, .jpg, .jpeg | `/api/v1/general/split-by-size-or-count` |
| `stirling_pdf.split_by_chapters` | standard | .pdf | .zip, .pdf, .png, .jpg, .jpeg | `/api/v1/general/split-pdf-by-chapters` |
| `stirling_pdf.auto_split` | standard | .pdf | .zip, .pdf, .png, .jpg, .jpeg | `/api/v1/misc/auto-split-pdf` |
| `stirling_pdf.split_by_sections` | standard | .pdf | .zip, .pdf, .png, .jpg, .jpeg | `/api/v1/general/split-pdf-by-sections` |
| `stirling_pdf.poster` | standard | .pdf | .zip, .pdf, .png, .jpg, .jpeg | `/api/v1/general/split-for-poster-print` |
| `stirling_pdf.booklet` | standard | .pdf | .pdf | `/api/v1/general/booklet-imposition` |
| `stirling_pdf.multi_page_layout` | standard | .pdf | .pdf | `/api/v1/general/multi-page-layout` |
| `stirling_pdf.single_page` | standard | .pdf | .pdf | `/api/v1/general/pdf-to-single-page` |
| `stirling_pdf.overlay` | standard | .pdf | .pdf | `/api/v1/general/overlay-pdfs` |
| `stirling_pdf.page_numbers` | standard | .pdf | .pdf | `/api/v1/misc/add-page-numbers` |
| `stirling_pdf.watermark` | standard | .pdf | .pdf | `/api/v1/security/add-watermark` |
| `stirling_pdf.stamp` | standard | .pdf | .pdf | `/api/v1/misc/add-stamp` |
| `stirling_pdf.add_image` | standard | .pdf | .pdf | `/api/v1/misc/add-image` |
| `stirling_pdf.add_comments` | standard | .pdf | .pdf | `/api/v1/misc/add-comments` |
| `stirling_pdf.replace_text` (before 3.3.0 only) | standard | .pdf | .pdf | `/api/v1/general/edit-text` |
| `stirling_pdf.metadata` | standard | .pdf | .pdf | `/api/v1/misc/update-metadata` |
| `stirling_pdf.bookmarks` | standard | .pdf | .json | `/api/v1/general/extract-bookmarks` |
| `stirling_pdf.edit_bookmarks` | standard | .pdf | .pdf | `/api/v1/general/edit-table-of-contents` |
| `stirling_pdf.remove_images` | standard | .pdf | .pdf | `/api/v1/general/remove-image-pdf` |
| `stirling_pdf.invert_colors` | standard | .pdf | .pdf | `/api/v1/misc/replace-invert-pdf` |
| `stirling_pdf.scanner_effect` | standard | .pdf | .pdf | `/api/v1/misc/scanner-effect` |
| `stirling_pdf.decompress` | standard | .pdf | .pdf | `/api/v1/misc/decompress-pdf` |
| `stirling_pdf.auto_rename` | standard | .pdf | .pdf | `/api/v1/misc/auto-rename` |
| `stirling_pdf.extract_images` | standard | .pdf | .zip, .pdf, .png, .jpg, .jpeg | `/api/v1/misc/extract-images` |
| `stirling_pdf.extract_scans` | standard | .pdf | .zip, .pdf, .png, .jpg, .jpeg | `/api/v1/misc/extract-image-scans` |
| `stirling_pdf.list_attachments` | standard | .pdf | .json | `/api/v1/misc/list-attachments` |
| `stirling_pdf.extract_attachments` | standard | .pdf | .zip, .pdf, .png, .jpg, .jpeg | `/api/v1/misc/extract-attachments` |
| `stirling_pdf.add_attachments` | standard | .pdf | .pdf | `/api/v1/misc/add-attachments` |
| `stirling_pdf.delete_attachment` | standard | .pdf | .pdf | `/api/v1/misc/delete-attachment` |
| `stirling_pdf.rename_attachment` | standard | .pdf | .pdf | `/api/v1/misc/rename-attachment` |
| `stirling_pdf.batch_process_attachments` | standard | .pdf | .pdf | `/api/v1/misc/batch-process-attachments` |
| `stirling_pdf.create_portfolio` | standard | .pdf | .pdf | `/api/v1/misc/create-portfolio` |
| `stirling_pdf.flatten_portfolio` | standard | .pdf | .pdf | `/api/v1/misc/flatten-portfolio` |
| `stirling_pdf.flatten` | standard | .pdf | .pdf | `/api/v1/misc/flatten` |
| `stirling_pdf.unlock_pdf_forms` | standard | .pdf | .pdf | `/api/v1/misc/unlock-pdf-forms` |
| `stirling_pdf.images_to_pdf` | standard | .png, .jpg, .jpeg, .tif, .tiff, .gif, .webp, .svg, .bmp | .pdf | `/api/v1/convert/img/pdf` |
| `stirling_pdf.pdf_to_img` | standard | .pdf | .zip, .png, .jpg, .jpeg, .tif, .tiff, .webp, .gif, .bmp | `/api/v1/convert/pdf/img` |
| `stirling_pdf.pdf_to_pdfa` | standard | .pdf | .pdf | `/api/v1/convert/pdf/pdfa` |
| `stirling_pdf.pdf_to_text` | standard | .pdf | .txt, .rtf | `/api/v1/convert/pdf/text` |
| `stirling_pdf.pdf_to_word` | standard | .pdf | .doc, .docx, .odt | `/api/v1/convert/pdf/word` |
| `stirling_pdf.file_to_pdf` | standard | .doc, .docx, .xls, .xlsx, .ppt, .pptx, .odt, .ods, .odp, .rtf, .txt | .pdf | `/api/v1/convert/file/pdf` |
| `stirling_pdf.pdf_to_presentation` | standard | .pdf | .ppt, .pptx, .odp | `/api/v1/convert/pdf/presentation` |
| `stirling_pdf.pdf_to_csv` | standard | .pdf | .csv, .zip | `/api/v1/convert/pdf/csv` |
| `stirling_pdf.pdf_to_xlsx` | standard | .pdf | .xlsx | `/api/v1/convert/pdf/xlsx` |
| `stirling_pdf.pdf_to_xml` | standard | .pdf | .xml | `/api/v1/convert/pdf/xml` |
| `stirling_pdf.html_to_pdf` | standard | .html, .htm, .zip | .pdf | `/api/v1/convert/html/pdf` |
| `stirling_pdf.markdown_to_pdf` | standard | .md, .markdown | .pdf | `/api/v1/convert/markdown/pdf` |
| `stirling_pdf.pdf_to_html` | standard | .pdf | .html, .zip | `/api/v1/convert/pdf/html` |
| `stirling_pdf.pdf_to_markdown` | standard | .pdf | .md, .zip | `/api/v1/convert/pdf/markdown` |
| `stirling_pdf.eml_to_pdf` | standard | .eml, .msg | .pdf | `/api/v1/convert/eml/pdf` |
| `stirling_pdf.svg_to_pdf` | standard | .svg | .pdf | `/api/v1/convert/svg/pdf` |
| `stirling_pdf.ebook_to_pdf` | standard | .epub, .azw3, .mobi | .pdf | `/api/v1/convert/ebook/pdf` |
| `stirling_pdf.pdf_to_epub` | standard | .pdf | .epub, .azw3 | `/api/v1/convert/pdf/epub` |
| `stirling_pdf.cbr_to_pdf` | standard | .cbr | .pdf | `/api/v1/convert/cbr/pdf` |
| `stirling_pdf.cbz_to_pdf` | standard | .cbz | .pdf | `/api/v1/convert/cbz/pdf` |
| `stirling_pdf.pdf_to_cbr` | standard | .pdf | .cbr | `/api/v1/convert/pdf/cbr` |
| `stirling_pdf.pdf_to_cbz` | standard | .pdf | .cbz | `/api/v1/convert/pdf/cbz` |
| `stirling_pdf.pdf_to_vector` | standard | .pdf | .ps, .eps, .pcl, .xps | `/api/v1/convert/pdf/vector` |
| `stirling_pdf.vector_to_pdf` | standard | .ps, .eps | .pdf | `/api/v1/convert/vector/pdf` |
| `stirling_pdf.pdf_to_ua` | standard | .pdf | .pdf | `/api/v1/convert/pdf/ua` |
| `stirling_pdf.url_to_pdf` | external | No local input | .pdf | `/api/v1/convert/url/pdf` |
| `stirling_pdf.analyze_basic_info` | standard | .pdf | .json | `/api/v1/analysis/basic-info` |
| `stirling_pdf.analyze_page_count` | standard | .pdf | .json | `/api/v1/analysis/page-count` |
| `stirling_pdf.analyze_page_dimensions` | standard | .pdf | .json | `/api/v1/analysis/page-dimensions` |
| `stirling_pdf.analyze_document_properties` | standard | .pdf | .json | `/api/v1/analysis/document-properties` |
| `stirling_pdf.analyze_font_info` | standard | .pdf | .json | `/api/v1/analysis/font-info` |
| `stirling_pdf.analyze_annotation_info` | standard | .pdf | .json | `/api/v1/analysis/annotation-info` |
| `stirling_pdf.analyze_form_fields` | standard | .pdf | .json | `/api/v1/analysis/form-fields` |
| `stirling_pdf.analyze_security_info` | standard | .pdf | .json | `/api/v1/analysis/security-info` |
| `stirling_pdf.pdf_info` | standard | .pdf | .json | `/api/v1/security/get-info-on-pdf` |
| `stirling_pdf.check_contains_text` | standard | .pdf | .pdf | `/api/v1/filter/filter-contains-text` |
| `stirling_pdf.check_contains_image` | standard | .pdf | .pdf | `/api/v1/filter/filter-contains-image` |
| `stirling_pdf.check_page_count` | standard | .pdf | .pdf | `/api/v1/filter/filter-page-count` |
| `stirling_pdf.check_page_size` | standard | .pdf | .pdf | `/api/v1/filter/filter-page-size` |
| `stirling_pdf.check_file_size` | standard | .pdf | .pdf | `/api/v1/filter/filter-file-size` |
| `stirling_pdf.check_page_rotation` | standard | .pdf | .pdf | `/api/v1/filter/filter-page-rotation` |
| `stirling_pdf.form_fields` | standard | .pdf | .json | `/api/v1/form/fields` |
| `stirling_pdf.form_fields_with_coordinates` | standard | .pdf | .json | `/api/v1/form/fields-with-coordinates` |
| `stirling_pdf.form_fill` | standard | .pdf | .pdf | `/api/v1/form/fill` |
| `stirling_pdf.form_extract_csv` | standard | .pdf | .csv | `/api/v1/form/extract-csv` |
| `stirling_pdf.form_extract_xlsx` | standard | .pdf | .xlsx | `/api/v1/form/extract-xlsx` |
| `stirling_pdf.form_add_fields` | standard | .pdf | .pdf | `/api/v1/form/add-fields` |
| `stirling_pdf.form_modify_fields` | standard | .pdf | .pdf | `/api/v1/form/modify-fields` |
| `stirling_pdf.form_edit_fields` | standard | .pdf | .pdf, .zip | `/api/v1/form/edit-fields` |
| `stirling_pdf.form_delete_fields` | standard | .pdf | .pdf | `/api/v1/form/delete-fields` |
| `stirling_pdf.form_detect` | standard | .pdf | .pdf, .json | `/api/v1/form/form-detection/detect` |
| `stirling_pdf.add_password` | sensitive | .pdf | .pdf | `/api/v1/security/add-password` |
| `stirling_pdf.remove_password` | sensitive | .pdf | .pdf | `/api/v1/security/remove-password` |
| `stirling_pdf.auto_redact` | sensitive | .pdf | .pdf | `/api/v1/security/auto-redact` |
| `stirling_pdf.redact` | sensitive | .pdf | .pdf | `/api/v1/security/redact` |
| `stirling_pdf.redact_execute` | sensitive | .pdf | .pdf | `/api/v1/security/redact-execute` |
| `stirling_pdf.cert_sign` | sensitive | .pdf | .pdf | `/api/v1/security/cert-sign` |
| `stirling_pdf.timestamp` | external | .pdf | .pdf | `/api/v1/security/timestamp-pdf` |
| `stirling_pdf.remove_cert_sign` | sensitive | .pdf | .pdf | `/api/v1/security/remove-cert-sign` |
| `stirling_pdf.sanitize` | standard | .pdf | .pdf | `/api/v1/security/sanitize-pdf` |
| `stirling_pdf.validate_signature` | standard | .pdf | .json | `/api/v1/security/validate-signature` |
| `stirling_pdf.verify` | standard | .pdf | .json | `/api/v1/security/verify-pdf` |
| `stirling_pdf.validate_compliance` | standard | .pdf | .json | `/api/v1/security/validate-compliance` |
| `stirling_pdf.accessibility_report` | standard | .pdf | .json | `/api/v1/security/accessibility-report` |
| `stirling_pdf.show_javascript` | standard | .pdf | .js | `/api/v1/misc/show-javascript` |
| `stirling_pdf.classify_and_label` | ai | .pdf | .pdf | `/api/v1/ai/tools/classify-and-label` |
| `stirling_pdf.math_auditor_agent` | ai | .pdf | .json | `/api/v1/ai/tools/math-auditor-agent` |
| `stirling_pdf.pdf_comment_agent` | ai | .pdf | .pdf | `/api/v1/ai/tools/pdf-comment-agent` |

## Deliberate boundaries

Sensitive, external and AI actions require a per-server opt-in. Hardware/server
certificate stores and PKCS#11 library paths are not exposed. Arbitrary endpoint
calls, account/team/database/billing administration, server-wide cleanup, pipeline
execution and document-index ingestion are not included. These need separate
permissions and lifecycle/response handling; they are not silently added here.
Single-attachment arbitrary-format downloads and the JSON-only AI HTML creation
agent are also not included. Archives are not extracted automatically. Do not
execute JavaScript extracted from a PDF.

## Sources

- [Official Stirling PDF 3.2.2 source](https://github.com/Stirling-Tools/Stirling-PDF/tree/684608d143779bf3a8ffc67639f077a1202c62ff)
- [Stirling PDF API specification](https://api.stirling.com/v1/api-docs)
- [Stirling PDF 3.3.0 release notes](https://github.com/Stirling-Tools/Stirling-PDF/releases/tag/v3.3.0)

The static catalog combines the official specification with source checks. It is
not downloaded or trusted dynamically at runtime. A 404 or a missing dependency
is an unsupported tool, not proof that the whole instance is offline.
