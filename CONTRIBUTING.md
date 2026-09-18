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

The development dependencies require Python 3.14 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --cov=custom_components/stirling_pdf --cov-report=term-missing --cov-fail-under=90
.\.venv\Scripts\ruff.exe check --no-cache custom_components tests
.\.venv\Scripts\ruff.exe format --check --no-cache custom_components tests
```

Hassfest and HACS validation also run in GitHub Actions.

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
