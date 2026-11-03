# Testing and compatibility evidence

This document distinguishes automated checks from manual observations. A high
coverage percentage, valid PDF header or successful config flow does not prove
every deployment and document works. No private PDF fixtures are used.

## Released baseline: 0.2.0

| Environment or check | Evidence | Scope |
|---|---|---|
| Home Assistant Core 2026.9.0 | Passing CI at the 0.2.0 release | Minimum-version integration suite, mocked server where appropriate |
| Home Assistant Core 2026.10.2 | Passing CI at the 0.2.0 release | Integration suite, strict per-module coverage, Ruff |
| Stirling PDF 3.2.0 container | Passing real-server CI at the 0.2.0 release | Status, health, API-key login enabled/disabled, merge, split, compress and synthetic Basic proxy |
| Community App 0.1.0 with Stirling PDF 2.14.3 | Maintainer's manual 0.2.0 acceptance run | Actual Supervisor-backed Basic login, four PDF actions, rejection reasons and output inspection |
| Existing standalone API-key deployment | Maintainer confirmed manual 0.2.0 regression test | Existing API-key-only use continued to work |
| Secret handling and persistence | Maintainer confirmed manual follow-up | Masked secrets, diagnostic redaction, retained entities/statistics across reload/restart |

These rows are separate checks, not proof of every combination in a full test
matrix. The native report does not capture the HA Core version automatically.
Do not infer a manual Core version from the separate CI rows.

## Historical additions: 0.3.0

Selected-page extraction and genuine OCR tests were added for 0.3.0.

- Extraction checks the exact selected page count, text and order on the real
  server, not only the PDF signature. It also uses the synthetic Basic proxy.
- OCR starts with a committed image-only page with no extractable text. The
  pinned standard server must produce searchable text containing known words
  and a number. Missing OCR capability fails the test rather than silently
  skipping it. English is requested; this does not prove other languages.
- Extraction client/service tests cover supported selection syntax, malformed
  selections, output validation, authentication failures and overwrite safety.
- The existing statistics reload test also covers the new operation value.
- Native HA example tests validate schema and templates without executing PDF
  actions or restarting a real Home Assistant installation.

CI continues to require 100% line coverage for `config_flow.py`, strictly more
than 95% for every other integration module, and a 95% overall floor. No coverage
exceptions or reduced thresholds are introduced for these features.

Before release, run [the native HA test](../examples/README.md) against both the
Community App and standalone API-key deployment with extraction enabled. Inspect
the selected PDF's actual content, all other outputs, exact rejection reasons,
diagnostic redaction, and retained statistics/entity IDs after reload/restart.
Do not treat the older 0.2.0 run as validation of the new extraction action.

## Maintainer-reported 0.3.0 acceptance, 2026-10-30

The maintainer reported successful runs on HA Core 2026.10.4, HAOS 18.4,
Supervisor 2026.10.5, aarch64, with integration version 0.3.0 in diagnostics:

| Deployment | Authentication | Successes | Exact rejections | Local counter |
|---|---|---|---|---|
| Community App, backend 2.14.3 | HTTP Basic | 6/6 | 8/8 | 15 to 21 |
| Standalone Docker, backend 3.2.2 | API key | 6/6 | 8/8 | 27 to 33 |

Generated files, selected-page content, trace rejection reasons, retained values
after reload/restart, masked credentials and redacted diagnostics were confirmed
by the maintainer. This does not validate the new 0.4.0 catalog.

## Development additions: 0.4.0, results pending

- Multiple entries, explicit routing, duplicate URL rejection and preservation
  of existing entry IDs, entity IDs and statistics.
- Per-server sensitive/external/AI opt-ins and 110 additional static contracts.
- Parameterized handler tests for each catalog entry, mixed upload fields,
  output containers, JSON/filter responses, permissions and limits.
- Optional diagnostics with listener-driven polling, endpoint deduplication and
  isolation from base status/reauthentication.
- Representative real HTTP and real-server cases for new tools.

Mocked handler tests do not validate all 110 server contracts. The catalog uses
official 3.2.2 source and the public OpenAPI document reporting 3.2.1. It must not
be described as fully tested on 2.14.3. No local Python, pip, pytest or Docker
execution was performed during preparation. Native Ruff and static JSON/catalog
checks are separate from CI and live tests. Coverage requirements are unchanged.

Before release, CI must pass on both supported HA test versions. Keep the existing
server entry, add the second server, and run the native script separately for
each selected server. The other server's counter must not change. Untargeted
actions must be rejected with two entries configured. Check reload/restart,
reconfigure/reauth isolation, optional-entity enabling/disabling and new tools in
small groups with non-private documents. Do not enable sensitive/network/AI groups
merely to make a general acceptance report green.

## Boundaries

- The synthetic Basic proxy is not the Community App or Supervisor.
- Real-server CI targets the pinned Stirling PDF 3.2.0 image, not every server
  release or architecture. The new action's API contract was checked in official
  2.14.3 and 3.2.0 source, but source compatibility is not an end-to-end test.
- There is no automatic OCR-quality score for arbitrary real-world scans.
- Invalid extraction syntax is checked locally. Page-count handling belongs to
  the server; the integration does not parse source PDFs or promise to detect
  every out-of-bounds selection before upload.
- OCR fixtures and optional regeneration instructions are documented under
  [tests_live/fixtures](../tests_live/fixtures/README.md). Node.js is only needed
  to regenerate the fixture, not to run Home Assistant or the Python CI suites.
