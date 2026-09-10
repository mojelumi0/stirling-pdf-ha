"""Validate the standalone custom-integration project files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
INTEGRATION = ROOT / "custom_components" / "stirling_pdf"
WORKFLOWS = ROOT / ".github" / "workflows"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _nested_keys(value: Any, prefix: str = "") -> set[str]:
    if not isinstance(value, dict):
        return {prefix}
    return {
        key
        for name, child in value.items()
        for key in _nested_keys(child, f"{prefix}.{name}" if prefix else name)
    }


def test_manifest_is_loadable_as_custom_integration() -> None:
    manifest = _load_json(INTEGRATION / "manifest.json")
    assert manifest["domain"] == "stirling_pdf"
    assert manifest["config_flow"] is True
    assert manifest["single_config_entry"] is True
    assert manifest["requirements"] == []
    assert manifest["codeowners"] == ["@mojelumi0"]
    assert manifest["documentation"].startswith("https://github.com/")
    assert manifest["issue_tracker"].endswith("/issues")


def test_service_and_translation_keys_match() -> None:
    services = yaml.safe_load(
        (INTEGRATION / "services.yaml").read_text(encoding="utf-8")
    )
    strings = _load_json(INTEGRATION / "strings.json")
    english = _load_json(INTEGRATION / "translations" / "en.json")
    german = _load_json(INTEGRATION / "translations" / "de.json")

    assert set(services) == {"merge", "split", "ocr", "compress"}
    assert set(strings["services"]) == set(services)
    assert set(english["services"]) == set(services)
    assert set(german["services"]) == set(services)
    for service, description in services.items():
        field_keys = set(description["fields"])
        assert set(strings["services"][service]["fields"]) == field_keys
        assert set(english["services"][service]["fields"]) == field_keys
        assert set(german["services"][service]["fields"]) == field_keys


def test_translation_structures_match() -> None:
    strings = _load_json(INTEGRATION / "strings.json")
    english = _load_json(INTEGRATION / "translations" / "en.json")
    german = _load_json(INTEGRATION / "translations" / "de.json")

    assert strings == english
    assert _nested_keys(english) == _nested_keys(german)


def test_hacs_manifest_is_valid() -> None:
    hacs = _load_json(ROOT / "hacs.json")

    assert hacs == {
        "name": "Stirling PDF",
        "homeassistant": "2026.9.0",
    }


def test_github_validation_workflows_exist() -> None:
    workflow_names = {"tests.yml", "hassfest.yml", "validate.yaml"}

    for name in workflow_names:
        workflow = (WORKFLOWS / name).read_text(encoding="utf-8")
        parsed = yaml.safe_load(workflow)
        assert isinstance(parsed, dict)
        assert "jobs" in parsed

    tests_workflow = (WORKFLOWS / "tests.yml").read_text(encoding="utf-8")
    assert 'python-version: "3.14"' in tests_workflow
    assert "python -m pytest" in tests_workflow
    assert "ruff check" in tests_workflow
    assert "ruff format --check" in tests_workflow

    hassfest_workflow = (WORKFLOWS / "hassfest.yml").read_text(encoding="utf-8")
    assert "home-assistant/actions/hassfest@master" in hassfest_workflow

    hacs_workflow = (WORKFLOWS / "validate.yaml").read_text(encoding="utf-8")
    assert "hacs/action@main" in hacs_workflow
    assert "category: integration" in hacs_workflow
