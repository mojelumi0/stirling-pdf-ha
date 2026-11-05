# Contributing

Thanks for helping improve Stirling PDF for Home Assistant.

## Before opening a pull request

1. Open or reference an issue that explains the Home Assistant use case.
2. Keep changes focused and avoid unrelated formatting rewrites.
3. Use only documented Stirling PDF endpoints and include the official source
   when adding or changing an endpoint.
4. Add or update tests for every behavior change.
5. Never commit API keys, private URLs, real documents, or unredacted logs.

## Local checks

The development dependencies require Python 3.14.2 or newer. Use Linux for the
full Home Assistant test environment.

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q -p no:cacheprovider --cov=custom_components/stirling_pdf --cov-report=term-missing --cov-report=json:coverage.json --cov-fail-under=95
.venv/bin/python scripts/check_coverage.py coverage.json
.venv/bin/ruff check --no-cache custom_components scripts tests tests_live
.venv/bin/ruff format --check --no-cache custom_components scripts tests tests_live
```

Hassfest and HACS validation also run in GitHub Actions.

The coverage gate requires 100% line coverage for `config_flow.py` and more than
95% for every other integration module. A high total cannot compensate for an
uncovered module. Keep the report complete; do not weaken the thresholds or add
coverage exclusions just to make a change pass. Test failures and recovery in
the same config flow, not only the first displayed error. Multiple entries use
normalized URL duplicate detection. Existing unique IDs, entry IDs, entity IDs
and per-entry statistics are not migrated or replaced.

CI tests Home Assistant 2026.9.0 with `requirements-dev-min.txt` and 2026.10.2
with `requirements-dev.txt`. Keep their framework pins aligned with the
Home Assistant versions in the workflow; shared pytest dependencies live in
`requirements-dev-common.txt`.

Home Assistant 2026.11 preparation is tracked separately in
[`docs/HA_2026_11.md`](docs/HA_2026_11.md). The manual readiness workflow needs an
exact upstream test-plugin version whose dependencies resolve with Core
2026.11.0. Never bypass the resolver with `--no-deps` or dependency overrides,
silence failures with `continue-on-error`, or count a prepared/skipped job as a
compatibility result. Preserve the two automatic jobs and their aggregate
`pytest` check. Add the stable 2026.11 job to that matrix after its test package
and a real passing result are available.

Base and optional metric entities use the cross-version `DeviceInfo(...)` constructor.
Keep device information as typed constructor arguments, not plain dictionaries
or dict-style mutation. The regression suite must cover registry-driven entity
ID changes and device display-name changes without losing coordinator updates,
stable registry IDs or saved operation statistics. Do not assert a complete
`friendly_name` string: Home Assistant owns display-name composition.

The Marketplace still reads `hacs.json` and uses the HACS validation action.
Keep the older `hacs_repository` My link while older HA versions are supported.
Check the documented category identifier rather than inventing one, and never
describe a custom repository as accepted into the public catalog without the
corresponding catalog merge. A Marketplace listing is not Core inclusion or a
security audit by the Home Assistant project.

Real-server contract tests live in `tests_live/` and use
`requirements-live.txt` in a separate environment. See the README for the
required test-server environment variables. They deliberately avoid real
documents and run with both enabled and disabled server authentication.

Keep both digest-pinned 3.2.0 and 3.3.0 server versions in the matrix, each with
both login modes. Pass `STIRLING_PDF_EXPECTED_VERSION` and verify the actual
reported version. Do not replace the older baseline or use a floating `latest`
tag. Version-specific removed-route/validation checks must clearly identify
their scope, not hide failures behind generic skips.

Version guards use the explicitly selected entry's cached status. Unknown,
custom and pre-release strings do not prove compatibility for restricted
actions/options. Test rejection before file I/O, network calls and statistics
changes, plus multi-server isolation and older-server behavior. The legacy text
editor remains registered for older deployments; no new Text Editor API is
assumed. Keep UI metadata, translations and contract fields aligned.

Converter fields default explicitly to false so a server-default change cannot
silently select the new converter. New 3.3.0 choices still require the existing
per-server opt-in and admin checks. Mocked wire-field tests do not establish
real Office/email/ebook/PDF/A rendering quality or complete SSRF protection.

The real-server suite includes selected-page extraction and OCR from a committed
image-only synthetic scan. Do not replace it with an already-searchable PDF or
skip OCR when the pinned standard image lacks its expected capability. Fixture
provenance and optional Node.js regeneration are documented in
`tests_live/fixtures/README.md`; the generator is not a runtime/CI dependency.

The native acceptance script is under `examples/`. Keep its name and report
version-independent. CI validates its HA schema, renders templates and checks
safe output targets, but real HA execution and manual trace/output checks remain
required. Record evidence honestly in `docs/TESTING.md`, distinguishing historical
release validation from pending tests for newly added behavior.

`examples/ha_ocr_test.yaml` is a separate, explicitly targeted native HA script
for the committed image-only fixture. Its synthetic HA tests execute the whole
sequence with registered fake services, including response failures, early stops,
counter mismatches and cross-server isolation. Those tests are not real OCR.
For live acceptance, verify the fixture hash, run once per selected server,
check all six results and inspect/extract text from each output. Keep failed
attempts in the evidence; do not silently rerun until the report turns green.

Transport failures must use fixed categories without raw exception text or
configured URLs. Keep exception chains suppressed at that boundary. Test both
request entry and body-reading failures, and retain the real local HTTP test
that receives a complete POST then disconnects: the client must not reupload.
No retry is introduced for a non-idempotent processing request.

## Pull-request scope

A new action should include:

- an explicit contract in `operations.py` or a dedicated client method;
- typed validation and registration through `tools.py` or `__init__.py`;
- action metadata in `services.yaml`;
- English and German translations;
- API-client and Home Assistant service tests;
- README documentation and a sanitized example.

Do not add arbitrary endpoint execution or raw HTTP payload passthrough. Match
primary and extra multipart file fields to the official source. Distinguish
PDF/ZIP/images/Office containers, JSON responses and HTTP 204 filter non-matches.
Protect each local input/output using HA's allowlist and executor-based I/O.
Optional metrics must remain disabled by default and poll only subscribed groups.
Source-derived contracts and mocked-handler coverage are not real-server proof.

The maintainer reviews all submitted code and documentation before release,
including contributions initially prepared with AI assistance.
