# Stirling PDF 3.3.0 compatibility preparation

## Scope and evidence

This work starts from integration PR #11 commit
`db17afb8985cd4b7a872cb620e9e7c97076740b5`. Upstream tag `v3.3.0` was resolved
to `7825214811d98fd3ec260bf315cd998ecb73b36b`, not a moving main branch.
The maintainer reports installing 3.3.0 on the standalone Test-PC. This is not
an automatically verified version or a completed integration acceptance run.

The integration remains `0.4.0-alpha.1`, with multiple server entries, existing
entity IDs, credentials, per-entry statistics format and the same HA minimum.
No dependency pin or coverage threshold is weakened. Source inspection and
selected tests are not proof that all 115 actions work on every deployment.

## Removed legacy text editing

Upstream removed `/api/v1/general/edit-text` in 3.3.0. The registered HA
`replace_text` action remains for older servers rather than being deleted
globally. On a selected server reporting 3.3.0 or newer, it raises a translated
validation error before output validation, input reads, upload or statistics
changes. A compatibility rejection does not start reauthentication.

Unknown, custom or pre-release version strings cannot establish support for
this restricted tool and are rejected instead of guessed. Stable `v` prefixes,
legacy `appVersion` values and build metadata are recognized. Strings are
bounded before parsing. Unrestricted actions keep working with unknown versions.

The check uses the selected entry's last polled status. It is not live OpenAPI
discovery and cannot prove endpoint availability on custom builds. Let status
refresh after a server upgrade. A future Text Editor API needs a separate
reviewed contract; no replacement URL or payload is invented here.

## Explicit converter selection

Nine more existing actions expose `use_stirling_office_convert` from 3.3.0:

| HA action | Format family |
|---|---|
| `pdf_to_pdfa` | PDF/A; PDF/X retains its legacy converter |
| `pdf_to_xml` | PDF to XML |
| `html_to_pdf` | HTML/ZIP to PDF; native conversion ignores zoom |
| `markdown_to_pdf` | Markdown to PDF |
| `pdf_to_html` | PDF to HTML/ZIP |
| `pdf_to_markdown` | PDF to Markdown/ZIP |
| `eml_to_pdf` | EML/MSG to PDF |
| `ebook_to_pdf` | Ebook to PDF |
| `pdf_to_epub` | PDF to EPUB/AZW3 |

Enabling these nine choices requires a recognized stable version at least 3.3.0,
the existing external-action opt-in, and admin permission for user calls.
Permission checks precede file I/O. Earlier converter choices retain their
previous availability and dependency limitations.

**Default change:** all fourteen converter fields, including the earlier five,
now default to false. False is included in the multipart request. Omission no
longer follows the server's converter default. Users who relied on that default
must explicitly select true and satisfy the existing per-server opt-in and
admin requirements. Upstream `OfficeConversionService.legacy(Boolean)` confirms
that explicit false selects the legacy route and null follows the admin setting.

This can fail if the deployment lacks the requested converter. The integration
does not silently switch engines, install dependencies or bypass permissions.
Converters and embedded resources still require deployment-level network
controls. This is not a sandbox or a guarantee of arbitrary format fidelity.

## OCR and validation

The pinned 3.3.0 OCR source supports `skip-text` and maps it to `--skip-text`.
Our existing OCR action already sends it; no force-OCR default is introduced.
A searchable input can succeed without new recognition. Use the committed
image-only fixture and separate native OCR script to test actual recognition.

Upstream enforces more documented defaults and rejects invalid input more
consistently. Local limits are not relaxed. A new server-specific test submits
poster factor 11 to 3.3.0 and expects HTTP 400 before output generation.

## Automated test preparation

Server CI contains four combinations: 3.2.0 and 3.3.0, each with login enabled
and disabled. The older image digest is preserved. The official Docker registry
returned this OCI index digest for `stirlingtools/stirling-pdf:3.3.0`:

```text
sha256:ed7b1775c6706b5e5ea24fa6155f078eff1027bd35a17d21834e4407036025e6
```

Each job sets `STIRLING_PDF_EXPECTED_VERSION` and verifies the actual status
version against it. When omitted in local opt-in tests, the expected version
defaults to the historical 3.2.0 baseline, not to whatever the server returns.

Existing real-client tests still cover health/authentication, merge/split,
compression, extraction, real English scan OCR and a synthetic Basic proxy.
An additional synthetic Markdown conversion sends explicit false and requires
searchable PDF output on both versions. This is a representative legacy
conversion, not rendering coverage for all fourteen converter choices.

3.3.0 additionally verifies that the legacy text-editor route returns 404 and
the invalid poster factor returns 400. Those two new-version-specific checks
are explicitly skipped on 3.2.0; that is not a skipped 3.3.0 failure. These
jobs do not test the Community App or Supervisor end to end.

Prepared HA tests cover bounded version parsing, pre-I/O rejection, two-server
routing, new-choice rejection on older servers, all fourteen true/false/omitted
wire choices and existing admin/opt-in rules. Those HA tests mock HTTP results;
they do not prove Office/email/ebook/PDF/A conversion quality.

No local Python, pip, pytest or Docker execution was performed. Native Ruff and
static checks do not replace fresh CI. Earlier green checks on `db17afb` cannot
validate this new preparation. No new passing CI or live result is claimed here.

## Live acceptance still required

Confirm the test instance, back up before installing the prepared runtime, and
retain both existing entries. Installation and any Core restart are separate
authorized changes. Do not downgrade to single-server 0.3.x or delete entries.

1. Verify loaded integration version and backend 3.3.0 in redacted diagnostics.
   Record the Community App's backend version separately.
2. Run `ha_test.yaml`, `ha_tools_test.yaml` and `ha_ocr_test.yaml` separately for
   the selected Test-PC entry with non-sensitive inputs and unique outputs.
   Inspect every result and exact rejection reason. Keep the other entry idle
   and check its counters and last-operation timestamp remain unchanged.
3. On 3.3.0, call `replace_text` against test paths and expect the local removal
   error, no upload/output/statistics change. A generic connection failure does
   not count as successful compatibility validation.
4. Check unchanged masked secrets, redacted diagnostics, base reachability and
   optional monitoring independently. Unsupported optional endpoints are not
   proof of invalid base credentials.
5. Test converter choices separately with suitable synthetic formats, permissions
   and installed dependencies. PDF acceptance scripts do not cover all fourteen
   conversions. Do not enable all optional groups merely to make a report green.
6. Separately authorize reload/restart persistence checks. Compare count,
   operation, timestamp and entity IDs without rerunning processing scripts.

The earlier Community App connection failures remain a separate unresolved case.
Upgrading the standalone server does not establish their cause or fix.

## Official sources

- [3.3.0 release notes](https://github.com/Stirling-Tools/Stirling-PDF/releases/tag/v3.3.0)
- [Release comparison](https://github.com/Stirling-Tools/Stirling-PDF/compare/v3.2.2...v3.3.0)
- [Removed text editor](https://github.com/Stirling-Tools/Stirling-PDF/pull/8504)
- [Validation and defaults](https://github.com/Stirling-Tools/Stirling-PDF/pull/8464)
- [Converter options](https://github.com/Stirling-Tools/Stirling-PDF/pull/8761)
- [Output limits](https://github.com/Stirling-Tools/Stirling-PDF/pull/8676)
- [Pinned OCR controller](https://github.com/Stirling-Tools/Stirling-PDF/blob/7825214811d98fd3ec260bf315cd998ecb73b36b/app/core/src/main/java/stirling/software/SPDF/controller/api/misc/OCRController.java)
- [Pinned converter service](https://github.com/Stirling-Tools/Stirling-PDF/blob/7825214811d98fd3ec260bf315cd998ecb73b36b/app/core/src/main/java/stirling/software/SPDF/service/OfficeConversionService.java)
- [Official image registry](https://hub.docker.com/r/stirlingtools/stirling-pdf)
