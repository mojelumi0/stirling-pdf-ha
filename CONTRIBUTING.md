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
the same config flow, not only the first displayed error. This integration
deliberately uses a single-instance guard rather than a mutable URL/IP as its
config-entry unique ID.

CI tests Home Assistant 2026.9.0 with `requirements-dev-min.txt` and 2026.10.2
with `requirements-dev.txt`. Keep their framework pins aligned with the
Home Assistant versions in the workflow; shared pytest dependencies live in
`requirements-dev-common.txt`.

Real-server contract tests live in `tests_live/` and use
`requirements-live.txt` in a separate environment. See the README for the
required test-server environment variables. They deliberately avoid real
documents and run with both enabled and disabled server authentication.

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

## Pull-request scope

A new action should include:

- a client method in `api.py`;
- validation and registration in `__init__.py`;
- action metadata in `services.yaml`;
- English and German translations;
- API-client and Home Assistant service tests;
- README documentation and a sanitized example.

The maintainer reviews all submitted code and documentation before release,
including contributions initially prepared with AI assistance.
