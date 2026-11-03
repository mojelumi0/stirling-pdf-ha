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

## Experimental pre-release: 0.4.0-alpha.1, results pending

The next public build is planned as an alpha, not as the latest regular release.
Its tag, manifest version and release title must all be `0.4.0-alpha.1`.
GitHub's pre-release flag must be enabled. It may be tagged from the development
branch after CI and the initial smoke tests pass; merging to main is not required
for alpha distribution. Full acceptance, especially the additional tool catalog,
remains pending until the corresponding tests have actually been performed.
There is no automatic publication or release approval in this preparation.

- Multiple entries, explicit routing, duplicate URL rejection and preservation
  of existing entry IDs, entity IDs and statistics.
- Per-server sensitive/external/AI opt-ins and 110 additional static contracts.
- Parameterized handler tests for each catalog entry, mixed upload fields,
  output containers, JSON/filter responses, permissions and limits.
- Optional diagnostics with listener-driven polling, endpoint deduplication and
  isolation from base status/reauthentication.
- Representative real HTTP and real-server cases for new tools.
- Both native HA examples use English labels and reports. Their operation names,
  action payloads, input/output paths, expected counts and safety guards remain
  unchanged by the language update. HA-generated errors can follow the HA UI language.

Mocked handler tests do not validate all 110 server contracts. The catalog uses
official 3.2.2 source and the public OpenAPI document reporting 3.2.1. It must not
be described as fully tested on 2.14.3. No local Python, pip, pytest or Docker
execution was performed during preparation. Native Ruff and static JSON/catalog
checks are separate from CI and live tests. Coverage requirements are unchanged.

Before alpha publication, CI must pass on both supported HA test versions and
initial smoke checks must verify the existing actions and basic multi-server
routing. The broader acceptance sequence below remains required before promoting
the tested feature scope to a regular `0.4.0` release. Keep the existing
server entry, add the second server, and run the native script separately for
each selected server. The other server's counter must not change. Untargeted
actions must be rejected with two entries configured. Check reload/restart,
reconfigure/reauth isolation, optional-entity enabling/disabling and new tools in
small groups with non-private documents. Do not enable sensitive/network/AI groups
merely to make a general acceptance report green.

## Alpha CI findings and fixes, 2026-11-03

The maintainer supplied failed CI logs for commit
`872fa07f06e64d7627c06046389b7e6f937a6a35`. Both supported HA jobs reported
481 passed and two failed tests. Every integration module reached 100% line
coverage, but the suites still failed. Coverage does not replace passing tests.
Hassfest rejected camelCase service translation keys. Both login modes of the
pinned real-server suite reported 19 passed and one failed test.

The correction was prepared against development commit
`2d65c6aa017634ee2e787d9704faf6c356476874`:

- Expose additional HA action fields in `snake_case`, consistently across schemas,
  selectors, translations and the native tool example. Map them back to original
  API names for multipart text fields and additional file uploads. Preserve the
  five established actions, API contracts, security opt-ins and URL checks.
- Instantiate actual selectors when validating documented defaults. The HA
  `validate_selector` helper returns a configuration dictionary, not a callable.
- Generate contract-test numeric inputs within their declared bounds. Keep the
  flattening minimum of 72 DPI, and explicitly test acceptance at 72 and rejection
  at 71. Do not relax the runtime constraint to accommodate an invalid fixture.
- Send `pageNumbers=all` in direct text-filter HTTP tests. The pinned 3.2.0 server
  dereferences the missing selection rather than defaulting it. Test both a PDF
  match (200 with verified content) and a non-match (204 with an empty body).
- Check public-name validity, uniqueness and agreement with service metadata,
  original wire names for every additional handler, and native example payloads.
  Retain the English report tests and documentation from local preparation.

These fixes were initially prepared without a successful CI rerun. No Python,
pytest, hassfest or Docker server was executed locally. The GitHub checks were
subsequently verified as successful on PR #11 head
`03fbf8f7ec156d2c777262572d6f548e6634a6fa`: both configured HA versions,
the aggregate pytest job, hassfest, HACS and both server login modes. This is
historical evidence for that exact commit, not for the later changes below.

## PR #11 independent review and regression preparation, 2026-11-03

The current published head was fetched again and matched all 69 local project
files before editing. The following fixes and regression tests were prepared:

- Require both the external-action opt-in and user-admin authorization when
  `use_stirling_office_convert` is true. Test every one of the five affected
  conversion services with non-admin and unknown users, before file access,
  output validation, network calls or statistics changes. Separately cover admin
  and internal automation calls, disabled opt-in, and ordinary local conversions.
  Keep HA's existing behavior for automation calls without a user context.
- Reject fractional, boolean and non-finite integer inputs, including nested
  integer arrays and integer enums. Preserve whole numbers and integer strings.
  Apply the same validator to the established compression-level action, where
  the independent review found the same truncation issue. Preserve range checks.
- Convert malformed or overflowing general numeric values to schema errors
  rather than allowing booleans or leaking raw conversion exceptions.
- Enforce the 4 MiB JSON-output limit in the common format validator, including
  `auto_rotate` and `form_detect`, before decoding/parsing or writing. Exercise
  boundaries below, exactly at and above the limit through HA's real service
  registry. Rejected outputs must not create files, replace existing outputs or
  update statistics. Pure JSON analysis remains covered too. Tests use a small
  patched limit, exercising the production logic without large fixtures.
- Do not apply that JSON-specific limit to PDF output. This remains a response
  validation limit after download, not a streaming memory cap.
- Do not change the production config flow for the reported legacy server-name
  issue: both credential preparation and normalization already preserve submitted
  fields. Add regression tests for legacy/current entries, successful renaming,
  failed validation and retry. The existing name-clearing test remains in place.

The review also inspected server routing, per-entry statistics, optional metric
isolation, output revalidation/atomic replacement and credential-safe HTTP error
handling. This is code inspection, not a claim that every server tool or deployment
has been validated. No automatic merge or release approval follows from it.

These tests were not executed locally. The subsequent GitHub checks were verified
as successful on head `8522362cfb48e356d6639424a0d7bcb369a1c9db`, including both
HA versions, existing coverage gates, hassfest/HACS and both real-server modes.
Copilot marked the four earlier discussions resolved. This is historical evidence
for that commit, not validation of the following metrics patch or live HA acceptance.

## Optional metric integer overflow follow-up, 2026-11-03

The updated review identified another real edge case: `math.isfinite` converts
integer arguments to float, which can overflow for very large JSON integers.
Simply accepting every Python integer would move the exception into HA's own
numeric sensor validation, which also calls `isfinite`. HA also limits state
strings to `MAX_LENGTH_STATE_STATE` (255 characters in both supported versions).

- Validate non-negative integers with direct integer comparisons, not a float or
  string conversion. Preserve valid integer values exactly. Return `None` for
  integers beyond the smaller of HA's state-text bound and the finite-float range,
  making the affected optional sensor unavailable instead of raising or rounding.
- Continue using `math.isfinite` only for float metric values. Keep rejection of
  booleans, negatives, non-finite floats and invalid types. Boolean capability
  sensors still accept actual `False` values.
- Bound uptime strings before integer parsing and route calculated seconds
  through the same numeric validation. This also avoids Python's integer-text
  limit on malformed, excessively long duration components.
- Add direct/mapping tests for ordinary counters, integers above float range,
  values above Python's integer-text limit, the exact HA state-length boundary,
  invalid floats and overlong uptime data.
- Enable one optional metric through the real entity registry before integration
  setup. Use its real platform/coordinator/state-machine path to test a valid
  value, an unavailable value and recovery. Also test publishing the largest
  accepted integer. Base status and local processing statistics must not change.

All HTTP interactions in those tests remain mocked. No live HA configuration is
changed. The new tests have not been executed locally; Ruff/static checks and
package hashes are separate from the required new CI run. The previous green
head does not validate this patch. No coverage thresholds or dependencies change.

## Native script discovery correction, 2026-11-03

GitHub checks for the metrics fix were subsequently verified as successful on
head `1852e56fa6e7103b228e8e666f99da51bd84975e`. The maintainer then reported an
actual HA acceptance-script failure: `config_entry_entities` is undefined. That
helper is not registered in either supported HA template environment. Previous
example tests rendered cases and reports but missed the first variables action.

Both native examples now use supported registry template APIs: obtain candidates
through the selected entry's title, then filter each entity's owning entry ID
with `config_entry_id` as a filter. This avoids title collisions and the script
input shadowing the template global of the same name. A string guard also avoids
mistaking HA's global function for input when no `config_entry_id` was supplied.
Invalid or foreign entry IDs produce no candidates and reach the existing safe
stop. The main script retains its single-server fallback; the additional-tools
script still requires an explicit selection.

New tests render the complete first variables action sequentially through HA's
`ScriptVariables`, using real template functions and entity registries rather
than mocked helper names. They cover both server selections, identical friendly
names including a foreign integration, absent/invalid selection, candidate sensor
roles and the preflight stop. The existing action-payload, case, report and safe
output tests remain in place. No PDF action or real server is executed by these
new discovery tests.

This correction changes only the examples, their tests and documentation, not
integration runtime code or dependencies. Users must separately replace the UI
YAML of scripts they already copied; a GitHub push cannot update those scripts.
The new tests have not been run locally and require a fresh CI run. Earlier green
checks are not evidence that the corrected initial discovery has passed.

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
