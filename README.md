# Stirling PDF for Home Assistant

Bring a self-hosted Stirling PDF instance into Home Assistant with native PDF
processing actions, connectivity monitoring, and a simple UI-based setup.

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?logo=home-assistant)](https://my.home-assistant.io/redirect/hacs_repository/?owner=mojelumi0&repository=stirling-pdf-ha&category=integration)
[![Tests](https://github.com/mojelumi0/stirling-pdf-ha/actions/workflows/tests.yml/badge.svg)](https://github.com/mojelumi0/stirling-pdf-ha/actions/workflows/tests.yml)
[![Hassfest](https://github.com/mojelumi0/stirling-pdf-ha/actions/workflows/hassfest.yml/badge.svg)](https://github.com/mojelumi0/stirling-pdf-ha/actions/workflows/hassfest.yml)
[![HACS validation](https://github.com/mojelumi0/stirling-pdf-ha/actions/workflows/validate.yaml/badge.svg)](https://github.com/mojelumi0/stirling-pdf-ha/actions/workflows/validate.yaml)

[Install with HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=mojelumi0&repository=stirling-pdf-ha&category=integration)
· [Report an issue](https://github.com/mojelumi0/stirling-pdf-ha/issues)
· [Stirling PDF](https://www.stirlingpdf.com/)

> [!WARNING]
> This integration is in an early test phase. Use copies of non-sensitive PDF
> files until it has been verified with more Home Assistant and Stirling PDF
> versions.

## What this integration does

Stirling PDF already provides a powerful local PDF processing API. This custom
integration makes a focused set of those operations available as native Home
Assistant actions, ready for scripts and automations.

- Local communication directly between Home Assistant and Stirling PDF
- Configuration through the Home Assistant UI
- Optional Stirling PDF API-key authentication
- Automatic connection validation and reauthentication
- Merge, split, OCR, and compression actions
- Connectivity, version, and local operation-status entities
- No cloud service required
- English and German user-interface translations

## Requirements

- Home Assistant 2026.9.0 or newer
- A reachable Stirling PDF instance
- HACS for the recommended installation method
- A directory that Home Assistant can read and write
- An API key when authentication is enabled in Stirling PDF

The Stirling PDF URL must be reachable from **Home Assistant itself**. Do not
use `localhost` unless Stirling PDF is running in the same network namespace as
Home Assistant.

## Installation

### HACS

1. Select **Install with HACS** above, or open HACS and add this repository as a
   custom **Integration** repository:

   ```text
   https://github.com/mojelumi0/stirling-pdf-ha
   ```

2. Find **Stirling PDF** in HACS and select **Download**.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration**.
5. Search for **Stirling PDF**.

During the initial test phase, HACS can install the default branch even when no
GitHub release exists yet.

### Manual installation

1. Download this repository.
2. Copy `custom_components/stirling_pdf` to
   `/config/custom_components/stirling_pdf` in Home Assistant.
3. Restart Home Assistant.
4. Add **Stirling PDF** from **Settings → Devices & services**.

## Connecting to Stirling PDF

The setup form asks for the complete root URL and an optional API key.

| Field | Description | Example |
|---|---|---|
| URL | Root URL of Stirling PDF, without an API endpoint | `http://192.168.1.50:8080` |
| API key | Required only when API authentication is enabled | `••••••••` |

Supported URL examples:

| Setup | Example URL |
|---|---|
| Local IP address | `http://192.168.1.50:8080` |
| Local hostname | `http://stirling-pdf.local:8080` |
| Reverse proxy with HTTPS | `https://pdf.example.com` |
| Reverse proxy subpath | `https://example.com/stirling` |

The integration validates the connection with
`/api/v1/info/status`. The URL and API key can later be changed with
**Reconfigure** on the integration page.

## File access

Action paths always refer to files visible **inside Home Assistant**, not paths
inside the Stirling PDF container. For example, create `/config/pdf` and allow
Home Assistant to use it:

```yaml
homeassistant:
  allowlist_external_dirs:
    - /config/pdf
```

Restart Home Assistant after changing `configuration.yaml`.

Important behavior:

- Input files must use the `.pdf` extension.
- Merge, OCR, and compression outputs must use `.pdf`.
- Split output must use `.zip` because Stirling PDF returns an archive.
- The output directory must already exist.
- Existing output files are not replaced unless **Overwrite** is enabled.
- Enabled overwriting uses an atomic replacement to avoid partial output files.
- PDFs are temporarily held in Home Assistant memory while being transferred.

Home Assistant does not provide a general file picker for arbitrary server or
container paths. The action editor therefore uses text fields for these paths.

## Available entities

All entities belong to a single Stirling PDF service device.

| Entity | Type | Description |
|---|---|---|
| Reachable | Binary sensor | Whether the latest status request succeeded |
| Version | Diagnostic sensor | Version reported by Stirling PDF |
| Jobs processed | Sensor | Successful actions run through this integration since it was loaded |
| Last operation | Enum sensor | Most recent successful action, with a UTC timestamp attribute |

`Jobs processed` is a local Home Assistant counter. It does not include jobs
started from the Stirling PDF web interface and resets when the integration is
reloaded or Home Assistant restarts.

## Available actions

| Action | Purpose | Output |
|---|---|---|
| `stirling_pdf.merge` | Combine two or more PDFs in the supplied order | PDF |
| `stirling_pdf.split` | Split a PDF after page numbers or expressions | ZIP containing PDFs |
| `stirling_pdf.ocr` | Make a scanned PDF searchable | PDF |
| `stirling_pdf.compress` | Reduce PDF file size with levels 1 through 9 | PDF |

### Merge PDFs

```yaml
action: stirling_pdf.merge
data:
  file_paths:
    - /config/pdf/part-1.pdf
    - /config/pdf/part-2.pdf
  output_path: /config/pdf/merged.pdf
  overwrite: false
```

### Split a PDF

```yaml
action: stirling_pdf.split
data:
  file_path: /config/pdf/document.pdf
  page_numbers: "2,5"
  output_path: /config/pdf/document-split.zip
  overwrite: false
```

Stirling PDF also accepts split expressions such as `all`, ranges, and
functions such as `2n+1`. Support can vary between Stirling PDF versions, so
check the Swagger UI of the installed server when using advanced expressions.

### Run OCR

```yaml
action: stirling_pdf.ocr
data:
  file_path: /config/pdf/scan.pdf
  languages:
    - eng
    - deu
  output_path: /config/pdf/scan-searchable.pdf
  overwrite: false
```

Only language packages installed in Stirling PDF can be used. Start with `eng`;
use `deu` for German when that Tesseract language is installed.

### Compress a PDF

```yaml
action: stirling_pdf.compress
data:
  file_path: /config/pdf/large.pdf
  optimize_level: 5
  output_path: /config/pdf/compressed.pdf
  overwrite: false
```

Optimization levels range from `1` to `9`. Higher levels can reduce quality and
take longer to process.

## API mapping

| Action | Stirling PDF endpoint |
|---|---|
| Status | `/api/v1/info/status` |
| Merge | `/api/v1/general/merge-pdfs` |
| Split | `/api/v1/general/split-pages` |
| OCR | `/api/v1/misc/ocr-pdf` |
| Compress | `/api/v1/misc/compress-pdf` |

The local Swagger UI at `<STIRLING-PDF-URL>/swagger-ui.html` is the best source
for the exact API supported by the installed Stirling PDF version.

## Troubleshooting

### The integration is not found after downloading

- Confirm that HACS placed the files in
  `/config/custom_components/stirling_pdf`.
- Restart Home Assistant after the HACS download.
- Refresh the browser before searching for the integration again.

### Home Assistant cannot connect

- Open `<STIRLING-PDF-URL>/api/v1/info/status` from the Home Assistant network.
- Use the complete URL including `http://` or `https://` and the port.
- Do not use `localhost` for a different container or computer.
- Check the API key when Stirling PDF security is enabled.

### A file path is rejected

- Use an absolute path visible from Home Assistant.
- Add the parent directory to `allowlist_external_dirs`.
- Confirm that Home Assistant can read inputs and write to the output directory.
- Use `.zip` for split output and `.pdf` for the other outputs.

### OCR fails

- Verify that every requested Tesseract language is installed in Stirling PDF.
- Test the same PDF and languages in the Stirling PDF web interface.
- Check the server's Swagger UI when using a different Stirling PDF release.

### Debug logging

Enable temporary debug logging in `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.stirling_pdf: debug
```

Restart Home Assistant, reproduce the problem, and remove debug logging when
finished. Never publish logs containing API keys, private URLs, or document
information.

## Known limitations

- Only one Stirling PDF instance can currently be configured.
- Operation statistics are local and are not persisted across restarts.
- There is no browser-based file picker for Home Assistant host paths.

## Support

- [Report a bug](https://github.com/mojelumi0/stirling-pdf-ha/issues/new)
- [Request a feature](https://github.com/mojelumi0/stirling-pdf-ha/issues/new)
- [Stirling PDF documentation](https://docs.stirlingpdf.com/)
- [Home Assistant community](https://community.home-assistant.io/)

When reporting a problem, include the Home Assistant version, Stirling PDF
version, installation method, action used, and sanitized error message.

## Official references

- [Stirling PDF API documentation](https://docs.stirlingpdf.com/API/)
- [Stirling PDF OpenAPI reference](https://registry.scalar.com/@stirlingpdf/apis/stirling-pdf-processing-api/)
- [Stirling PDF source code](https://github.com/Stirling-Tools/Stirling-PDF)
- [Home Assistant integration manifest](https://developers.home-assistant.io/docs/creating_integration_manifest/)
- [Home Assistant integration actions](https://developers.home-assistant.io/docs/dev_101_services/)
- [Home Assistant config flow](https://developers.home-assistant.io/docs/core/integration/config_flow/)
- [HACS integration repository requirements](https://hacs.xyz/docs/publish/integration/)

## Disclaimer

This is an independent community integration and is not an official project of
Stirling PDF, Home Assistant, or HACS.
