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
- Optional response data for scripts and automations
- Connectivity, version, and persistent local operation-status entities
- Privacy-aware diagnostics for easier troubleshooting
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

The current releases are prereleases. If HACS does not offer the newest alpha
version, enable the `switch.stirling_pdf_pre_release` entity under
**Settings → Devices & services → Entities**, then refresh the update
information in HACS.

The HACS update dialog can currently show **Icon not available** even though the
integration icon appears correctly elsewhere in Home Assistant. This is a
known HACS frontend issue and does not affect the integration. See
[HACS issue #5223](https://github.com/hacs/integration/issues/5223).

### Manual installation

1. Download this repository.
2. Copy `custom_components/stirling_pdf` to
   `/config/custom_components/stirling_pdf` in Home Assistant.
3. Restart Home Assistant.
4. Add **Stirling PDF** from **Settings → Devices & services**.

### Removing the integration

1. Disable or update scripts and automations that call `stirling_pdf` actions.
2. In **Settings → Devices & services**, open Stirling PDF and delete its
   integration entry. This removes its entities and permanently deletes the
   integration's locally saved job count and last-operation details. Make a
   Home Assistant backup first if you want to retain the option to restore them.
3. Remove the downloaded integration from HACS. For a manual installation,
   remove only `/config/custom_components/stirling_pdf` instead.
4. Restart Home Assistant after removing the integration files.

Removing the integration does **not** delete your input PDFs, generated PDF/ZIP
files, or the separate Stirling PDF server. Remove an `allowlist_external_dirs`
entry only if no other integration or automation still needs that directory.

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

The integration validates reachability with `/api/v1/info/status` and checks
API access through the read-only `/api/v1/info/health` endpoint. In Stirling PDF
3.2.0, status is public while health requires authentication when login is
enabled. No PDF is uploaded or processed during this check.

If health returns HTTP 404, 405, or 501, the integration falls back to the status
check for compatibility. Diagnostics then report
`authentication_check_supported: false`; a successful setup in this case does
not confirm permission to process PDFs. A successful health check also cannot
guarantee that every individual PDF tool is enabled or allowed.

The URL and API key can later be changed with
**Reconfigure** on the integration page.

For security, an already saved API key is never sent back to the reconfigure
form. A masked placeholder means that a key is stored. Leave the placeholder
unchanged to keep the key, enter a new value to replace it, or clear the field
to remove it. Reauthentication always starts with an empty API-key field.

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
- The Home Assistant allowlist, required file extensions, existing destinations,
  and the output directory are checked before inputs are read or PDFs are uploaded.
  This check does not create an output file.
- Destination checks are repeated when saving because paths can change while
  Stirling PDF is processing. Passing the initial check does not guarantee that
  the final write will succeed.
- Enabled overwriting uses an atomic replacement to avoid partial output files.
- PDFs are temporarily held in Home Assistant memory while being transferred.

Home Assistant does not provide a general file picker for arbitrary server or
container paths. The action editor therefore uses text fields for these paths.

## Available entities

All entities belong to a single Stirling PDF service device.

| Entity | Type | Description |
|---|---|---|
| Reachable | Binary sensor | Whether the latest status and supported API-access checks succeeded |
| Version | Diagnostic sensor | Version reported by Stirling PDF |
| Jobs processed | Sensor | Persisted count of successful actions run through this integration |
| Last operation | Enum sensor | Most recent successful action, with a UTC timestamp attribute |

`Jobs processed` is a local Home Assistant counter. It does not include jobs
started from the Stirling PDF web interface. The counter and last-operation
details are saved and restored across integration reloads and Home Assistant
restarts.

### Updates and availability

The integration polls the status endpoint every **60 seconds** and also checks
the health endpoint when supported. This interval is fixed; there is currently
no polling-interval option in the UI. A change on the server may therefore take
until the next successful poll to appear in Home Assistant.

If a poll fails, **Reachable** becomes off and **Version** becomes unavailable.
The locally stored **Jobs processed** and **Last operation** entities remain
available. Polling resumes automatically after connection failures; rejected
credentials instead trigger Home Assistant's reauthentication flow.

Successful PDF actions update the local statistics after the output has been
saved, without waiting for a poll. Failed actions do not count as completed
jobs. Reloading the integration or restarting Home Assistant preserves these
statistics; deleting the integration entry removes them.

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

### Action response data

Every action can optionally return data to a Home Assistant script or
automation. The response contains:

| Field | Description |
|---|---|
| `operation` | Completed action: `merge`, `split`, `ocr`, or `compress` |
| `output_path` | Path of the generated file |
| `output_size` | Size of the generated file in bytes |
| `input_count` | Number of input files processed |

Use `response_variable` when the result is needed by later steps:

```yaml
action: stirling_pdf.compress
data:
  file_path: /config/pdf/large.pdf
  optimize_level: 5
  output_path: /config/pdf/compressed.pdf
response_variable: stirling_result
```

For example, `{{ stirling_result.output_size }}` then contains the output size
in bytes. The response is optional, so existing scripts continue to work
unchanged.

## API mapping

| Action | Stirling PDF endpoint |
|---|---|
| Status | `/api/v1/info/status` |
| API access check | `/api/v1/info/health` |
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

### The status endpoint is disabled

The integration needs `/api/v1/info/status` for setup and availability
monitoring. If Stirling PDF reports that this endpoint is disabled, enable the
status endpoint in the Stirling PDF configuration, restart Stirling PDF, and
then try the setup again. See the
[upstream Stirling PDF issue](https://github.com/Stirling-Tools/Stirling-PDF/issues/5493)
for background.

### The server is reachable, but PDF actions reject the API key

A public status response does not prove permission to process documents.
Starting with 0.1.4-alpha, setup, reconfiguration, reauthentication, and periodic
updates also check the health endpoint when available. If a PDF action returns
HTTP 401 or 403, Home Assistant starts a reauthentication flow. Open
**Settings → Devices & services** and enter a valid Stirling PDF API key.
The failed action is not automatically retried and does not increase the local
job counter. After updating the key, run the action again.

A 403 response can also mean an account or access restriction. If replacing
the key does not help, check permissions on the Stirling PDF server.

### A compression value is rejected with “Got None”

Optimization levels must be integers from 1 through 9. Home Assistant may append
“Got None” to its validation message for an invalid value. This does not mean
that a PDF was processed successfully or that the job counter should increase.

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

### Download diagnostics

Open **Settings → Devices & services → Stirling PDF**, open the three-dot menu,
and select **Download diagnostics**. The diagnostic file includes status and
local operation information while automatically removing the API key and
configured server URL. Review diagnostic files before sharing them publicly.

## Known limitations

- Only one Stirling PDF instance can currently be configured.
- Operation statistics only count actions started through this integration.
- There is no browser-based file picker for Home Assistant host paths.
- Password, watermark, and office-document conversion actions are not part of
  the first version.
- Compatibility with additional Home Assistant and Stirling PDF versions still
  needs broader community testing.

## Development

Use Linux and Python 3.14.2 or newer for the full Home Assistant test environment,
or let the repository's GitHub Actions run it:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q -p no:cacheprovider --cov=custom_components/stirling_pdf --cov-report=term-missing --cov-report=json:coverage.json --cov-fail-under=95
.venv/bin/python scripts/check_coverage.py coverage.json
.venv/bin/ruff check --no-cache custom_components scripts tests tests_live
.venv/bin/ruff format --check --no-cache custom_components scripts tests tests_live
```

The test suite covers URL handling, authentication, multipart requests,
response validation, manifests, HACS metadata, translations, workflow
structure, Home Assistant config flows, entity setup, unload behavior,
diagnostics, persistent statistics, and service actions. Flow tests include
correcting errors and completing the same setup, reconfigure, or reauthentication
flow. Additional tests cover malformed saved statistics, API timeouts, missing
inputs, and failed atomic output replacement.

GitHub Actions enforces **100% line coverage for `config_flow.py`** and
**more than 95% for each other integration Python module**, as well as a 95%
overall floor. The per-module checker uses exact covered/total line counts,
not rounded percentages. Every source module must appear in the report;
missing or malformed reports fail the check. Results and missing lines appear
in the workflow log and GitHub job summary. These are enforced CI targets,
not a claim that manual tests prove complete correctness.

The `Tests` workflow runs the Home Assistant suite against both the advertised
minimum (2026.9.0) and current tested Core version (2026.10.2), using separate
compatible dependency sets. Its final `pytest` job keeps the existing required
status-check name and only succeeds when both versions pass.

All workflows use Ubuntu 24.04 explicitly. Release-version validation checks
the actual release tag rather than a potentially newer default-branch commit.
After the first server-test run, the two `PDF server (login true/false)` checks
can also be selected as required checks in the branch ruleset.

### Real-server tests

The `Stirling PDF server tests` workflow starts a disposable, version-pinned
Stirling PDF 3.2.0 container with login enabled and disabled. It runs on pushes,
pull requests, manual dispatch, and weekly. It checks public status versus
protected health, missing and invalid API keys, merge ordering, Unicode
filenames, split ZIP contents, and compression while preserving page text.
These are real HTTP/API-client tests; Home Assistant action execution and
file handling are covered separately by the Home Assistant suite. OCR is
currently covered by client/service tests and the documented manual tests,
not by this container workflow.

To run the server tests locally, use a separate virtual environment with
`requirements-live.txt`, start a disposable Stirling PDF 3.2.0 server, and set:

```powershell
$env:STIRLING_PDF_URL = "http://127.0.0.1:8080"
$env:STIRLING_PDF_API_KEY = "<test-server-api-key>"
$env:STIRLING_PDF_REQUIRE_AUTH = "true"
python -m pytest -q -p no:cacheprovider tests_live
```

Use `"false"` for `STIRLING_PDF_REQUIRE_AUTH` when login is disabled. The tests
upload only synthetic PDFs. Without `STIRLING_PDF_URL`, server-dependent tests
are skipped. A Docker runtime is required to reproduce the container workflow.


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
- [Home Assistant integration diagnostics](https://developers.home-assistant.io/docs/core/integration/diagnostics/)
- [Home Assistant config flow](https://developers.home-assistant.io/docs/core/integration/config_flow/)
- [Stirling PDF 3.2.0 status and health controller](https://github.com/Stirling-Tools/Stirling-PDF/blob/v3.2.0/app/core/src/main/java/stirling/software/SPDF/controller/web/MetricsController.java)
- [Stirling PDF 3.2.0 authentication filter](https://github.com/Stirling-Tools/Stirling-PDF/blob/v3.2.0/app/proprietary/src/main/java/stirling/software/proprietary/security/filter/UserAuthenticationFilter.java)
- [HACS integration repository requirements](https://hacs.xyz/docs/publish/integration/)
- [Home Assistant config-flow test coverage](https://contributors.home-assistant.io/core/quality-scale/config-flow-test-coverage/)
- [Home Assistant per-module test coverage](https://contributors.home-assistant.io/core/quality-scale/test-coverage/)
- [Home Assistant parallel updates](https://contributors.home-assistant.io/core/quality-scale/parallel-updates/)
- [Home Assistant integration categories](https://contributors.home-assistant.io/core/integrations/categories/)

## Development transparency

This project is developed with support from AI tools, including ChatGPT and
Claude. I personally review the proposed code, documentation, and other project
files before publishing changes. AI assistance does not replace manual review,
testing, or maintainer responsibility, and mistakes can still happen. If you
spot something, please open an issue.

## Disclaimer

This is an independent community integration and is not an official project of
Stirling PDF, Home Assistant, or HACS.
