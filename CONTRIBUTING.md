# Contributing

Thanks for helping improve Stirling PDF for Home Assistant. Keep pull requests
focused and include tests for behavior changes. Use synthetic documents and
never commit credentials, private URLs, real PDFs or unredacted logs.

## Local checks

Use Python 3.14.2 or newer and Linux for the full Home Assistant test environment.

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q -p no:cacheprovider --cov=custom_components/stirling_pdf --cov-report=term-missing --cov-report=json:coverage.json --cov-fail-under=95
.venv/bin/python scripts/check_coverage.py coverage.json
.venv/bin/ruff check --no-cache custom_components scripts tests tests_live
.venv/bin/ruff format --check --no-cache custom_components scripts tests tests_live
```

CI checks both supported test baselines with `requirements-dev-min.txt` and
`requirements-dev.txt`, and runs hassfest and HACS validation. Keep 100% line
coverage for `config_flow.py` and more than 95% per other integration module.
The [manual HA 2026.11 workflow](.github/workflows/ha-2026-11.yml) requires an
exact compatible test-plugin version. Do not bypass dependency resolution or
count a skipped check as passing.

## Testing against Stirling PDF

The [server workflow](.github/workflows/server-tests.yml) tests digest-pinned
Stirling PDF versions with and without login. To run it locally, install
`requirements-live.txt` in a separate environment and use a disposable server:

```bash
export STIRLING_PDF_URL=http://127.0.0.1:8080
export STIRLING_PDF_API_KEY='<test-server-key>'
export STIRLING_PDF_REQUIRE_AUTH=true
export STIRLING_PDF_EXPECTED_VERSION=3.3.0
python -m pytest -q -p no:cacheprovider tests_live
```

Set the expected version to the backend you started. For a server without
login, omit the key and use `STIRLING_PDF_REQUIRE_AUTH=false`. The suite skips
server-dependent tests when no URL is set. It uses synthetic PDFs, including
an [image-only OCR fixture](tests_live/fixtures/README.md).

Use the [Home Assistant test scripts](examples/README.md) for acceptance on a
test instance. Record the versions, exact failures and checked outputs in the
PR. Mock tests and a successful retry are not proof of backend compatibility
or of a fix for the first failure.

## Changing actions

- Link the upstream endpoint contract. Update the action's validation,
  `services.yaml`, English and German translations, and tests together.
- Use allowlisted paths, explicit server selection, and typed inputs. Test
  invalid inputs, version restrictions, and isolation between server entries.
- Preserve entity IDs and saved statistics. Optional metrics stay disabled
  by default.
- Keep credentials and private URLs out of errors. Do not automatically
  retry processing requests: a disconnected client cannot know whether
  Stirling PDF already processed the upload.
