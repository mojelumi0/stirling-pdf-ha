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
.venv/bin/python -m pytest -q -p no:cacheprovider --cov=custom_components/stirling_pdf --cov-report=term-missing --cov-fail-under=90
.venv/bin/ruff check --no-cache custom_components tests tests_live
.venv/bin/ruff format --check --no-cache custom_components tests tests_live
```

Hassfest and HACS validation also run in GitHub Actions.

CI tests Home Assistant 2026.9.0 with `requirements-dev-min.txt` and 2026.10.2
with `requirements-dev.txt`. Keep their framework pins aligned with the
Home Assistant versions in the workflow; shared pytest dependencies live in
`requirements-dev-common.txt`.

Real-server contract tests live in `tests_live/` and use
`requirements-live.txt` in a separate environment. See the README for the
required test-server environment variables. They deliberately avoid real
documents and run with both enabled and disabled server authentication.

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
