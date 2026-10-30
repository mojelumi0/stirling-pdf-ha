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

> [!NOTE]
> This is an actively developed community integration with a focused feature
> set. Keep backups and use copies of documents when testing a new deployment.
> A regular release is not a guarantee of compatibility with every server setup.

## What this integration does

Stirling PDF already provides a powerful local PDF processing API. This custom
integration makes a focused set of those operations available as native Home
Assistant actions, ready for scripts and automations.

- Local communication directly between Home Assistant and Stirling PDF
- Configuration through the Home Assistant UI
- Optional Stirling PDF API-key authentication
- Optional HTTP Basic authentication for protected proxies and the Community App
- Automatic connection validation and reauthentication
- Merge, split, OCR, compression, and page-extraction actions
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
- HTTP Basic username and password when the direct API port or proxy requires them

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

Normal releases do not require opting into prereleases. To test a future
prerelease, enable the repository's pre-release switch in HACS. Leave it disabled
if you only want normal releases.

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

The setup form asks for the complete root URL and optional API-key or HTTP Basic
credentials. Use only the authentication methods required by your deployment.

| Field | Description | Example |
|---|---|---|
| URL | Root URL of Stirling PDF, without an API endpoint | `http://192.168.1.50:8080` |
| API key | Required only when API authentication is enabled | `••••••••` |
| HTTP Basic username | Required with the HTTP Basic password, if used | Your HA username for the Community App |
| HTTP Basic password | Required with the HTTP Basic username, if used | Stored as a masked secret |

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

The URL, API key and HTTP Basic credentials can later be changed with
**Reconfigure** on the integration page.

Saved API keys and passwords are never sent back to the forms. A masked
placeholder represents a secret held by the integration. Leave it unchanged to
keep that secret, replace it to update it, or clear it to remove it. To remove
HTTP Basic authentication, clear **both** its username and password. A failed
validation does not replace the saved configuration. Reauthentication starts
with empty secret fields: re-enter every credential the deployment requires.

### Stirling PDF Community App

The [Home Assistant Community App](https://github.com/hassio-addons/app-stirling-pdf)
protects its direct API port with **HTTP Basic authentication**, using your
Home Assistant username and password. Ingress browser authentication is a
different mechanism and cannot be used as the integration URL.

1. In Home Assistant, open **Settings > Apps > Stirling PDF > Configuration**.
2. Check **Network > Web interface & API**. If no host port is configured,
   assigning one changes the running app's network exposure. Review that change
   and your firewall first. The app documentation requires configuring the
   direct API port for direct access; do not assume Ingress exposes it.
3. Use your HA host address and configured direct host port, for example
   `http://192.168.1.50:8080`. The app documentation also gives the internal
   hostname `http://a0d7b954-stirling-pdf:8080` for HA REST commands; only use it
   if reachable in your installation. Never use an Ingress URL.
4. In the integration's **Reconfigure** form, enter that URL and your Home
   Assistant login username and password in the **HTTP Basic** fields. Use the
   actual username, not a display name or long-lived access token.
5. Leave the Stirling API-key field empty unless your deployment separately
   requires an API key. Both authentication methods can be used together.
6. Leave the app's **`leave_front_door_open` set to `false`**. There is no need
   to disable its authentication to use this integration.

HTTP Basic encodes credentials; it does **not encrypt** them. Prefer HTTPS with
a trusted certificate, or keep HTTP strictly inside a trusted, isolated local
network. Do not expose the direct API port to the internet or untrusted clients.
TLS certificate verification remains enabled; self-signed certificates must be
trusted by Home Assistant rather than bypassing verification in this integration.
The integration stores credentials in its Home Assistant config entry, not in
entities or automations. Masking is not encryption; protect your HA storage and
backups. Diagnostics redact the username, password, URL and API key.

Automatic HTTP redirects are refused on every API request. Enter the final
server URL, including the correct HTTPS scheme and any required subpath, so
credentials and documents cannot be forwarded to a redirect destination.
HTTP errors include their status and endpoint but not untrusted response bodies,
which could echo private information.

See the app's [official direct-access documentation](https://github.com/hassio-addons/app-stirling-pdf/blob/main/stirling-pdf/DOCS.md#direct-access)
for its current networking and authentication behavior. Automated proxy tests
do not replace testing the actual app and Supervisor authentication.

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
| `stirling_pdf.extract_pages` | Save selected pages in a new PDF | PDF |

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

### Extract selected pages

```yaml
action: stirling_pdf.extract_pages
data:
  file_path: /config/pdf/document.pdf
  page_numbers: "1,3-5"
  output_path: /config/pdf/selected-pages.pdf
  overwrite: false
```

Page numbers start at **1**. The action accepts positive page numbers and
ascending ranges separated by commas, with at most 1024 characters including
whitespace in the original input. Spaces around commas and hyphens are allowed.
A selection such as `4,1-2` requests that order. Stirling PDF may deduplicate
repeated page numbers.

Unlike `split`, extraction returns **one `.pdf` file**, not a ZIP. Its supported
selection syntax is deliberately limited to explicit pages/ranges: `all`,
functions such as `2n+1`, zero/negative pages and descending ranges are not
accepted. The existing split action's server-supported expressions are unchanged.

This uses the official `/api/v1/general/rearrange-pages` endpoint with
`customMode=CUSTOM`. The API contract was checked in Stirling PDF 2.14.3 and
3.2.0 source. That is not a claim that the development feature already passed
manual testing on every deployment. The integration validates syntax, not the
source PDF's page count. Inspect outputs when selecting pages beyond its length;
page-count handling is delegated to the server and can vary by version.

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
- Check the API key when Stirling PDF security is enabled, and HTTP Basic
  credentials when using the Community App or a protected proxy.

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

For the Community App, HTTP Basic authentication is separate from a Stirling
API key. Re-enter the actual HA login username and password in the Basic fields.
Leave the app's authentication enabled. After a rejected login, check the stored
configuration and use reauthentication/reconfiguration rather than deleting the
integration. Do not repeatedly retry invalid credentials or share their values.

### Extraction rejects a page selection

Use explicit positive pages or ascending ranges such as `1,3-5`. Extraction
does not accept `all` or function expressions. Clear accidental trailing commas
and do not use spaces inside a number. The server determines which selected
pages actually exist; a successful response alone does not prove all requested
pages were present.
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
finished. Never publish logs containing usernames, passwords, Authorization
headers, API keys, private URLs, or document information.

### Download diagnostics

Open **Settings → Devices & services → Stirling PDF**, open the three-dot menu,
and select **Download diagnostics**. The diagnostic file includes status and
local operation information while automatically removing the API key, HTTP Basic
username/password, known Authorization header fields and configured server URL.
Review diagnostic files before sharing them publicly.

## Testing your installation

Use the [native Home Assistant test script](examples/README.md) with copies of
`a.pdf` and `b.pdf` in an allowlisted test folder. It generates a report and
uniquely named outputs without deleting files, reloading the integration or
restarting HA. Its filename is independent of the installed integration version.

Keep page extraction enabled when accepting this development feature. With it
enabled, the complete run expects 6 successes, 8 deliberate rejections and a
counter increase of 6. Exact rejection reasons, output contents, credentials,
diagnostics, installed version and reload/restart persistence still need manual
inspection; the script is not an automatic merge/release approval.

See [testing and compatibility evidence](docs/TESTING.md) for the distinction
between released observations, CI checks and pending development validation.

## Known limitations

- Only one Stirling PDF instance can currently be configured.
- Operation statistics only count actions started through this integration.
- There is no browser-based file picker for Home Assistant host paths.
- Password, watermark, and office-document conversion actions are not implemented.
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
filenames, split ZIP contents, compression and selected-page extraction while
checking page content and order. A synthetic image-only scanned PDF exercises
real English OCR; the source has no searchable text and recognition must produce
known words and a number. These added development checks must pass in CI before
they can be counted as validation of the new release.
The same jobs also exercise a synthetic HTTP Basic proxy in front of the real
server, including combined API-key authentication and rejected Basic credentials.
Local HTTP transport tests cover all five client operations and refusal to
forward credentials or PDF uploads to redirect targets. These proxy/transport
tests are not end-to-end tests of the Community App or Supervisor itself.
These are real HTTP/API-client tests; Home Assistant action execution and
file handling are covered separately by the Home Assistant suite. OCR is also
covered by client/service and manual tests; one synthetic English scan does not
prove OCR quality for every document or installed language.

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
- [Stirling PDF Community App direct API access](https://github.com/hassio-addons/app-stirling-pdf/blob/main/stirling-pdf/DOCS.md#direct-access)
- [Home Assistant integration manifest](https://developers.home-assistant.io/docs/creating_integration_manifest/)
- [Home Assistant integration actions](https://developers.home-assistant.io/docs/dev_101_services/)
- [Home Assistant integration diagnostics](https://developers.home-assistant.io/docs/core/integration/diagnostics/)
- [Home Assistant config flow](https://developers.home-assistant.io/docs/core/integration/config_flow/)
- [Stirling PDF 3.2.0 status and health controller](https://github.com/Stirling-Tools/Stirling-PDF/blob/v3.2.0/app/core/src/main/java/stirling/software/SPDF/controller/web/MetricsController.java)
- [Stirling PDF 3.2.0 authentication filter](https://github.com/Stirling-Tools/Stirling-PDF/blob/v3.2.0/app/proprietary/src/main/java/stirling/software/proprietary/security/filter/UserAuthenticationFilter.java)
- [Stirling PDF 2.14.3 page selection controller](https://github.com/Stirling-Tools/Stirling-PDF/blob/v2.14.3/app/core/src/main/java/stirling/software/SPDF/controller/api/RearrangePagesPDFController.java)
- [Stirling PDF 3.2.0 page selection controller](https://github.com/Stirling-Tools/Stirling-PDF/blob/v3.2.0/app/core/src/main/java/stirling/software/SPDF/controller/api/RearrangePagesPDFController.java)
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
