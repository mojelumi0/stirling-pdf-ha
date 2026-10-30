"""Validate the native HA example without running PDF actions or restarting HA."""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml
from homeassistant.components.script.config import SCRIPT_ENTITY_SCHEMA
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def example() -> dict[str, Any]:
    return yaml.safe_load((ROOT / "examples" / "ha_test.yaml").read_text("utf-8"))


def _render(hass: HomeAssistant, value: Any, context: dict[str, Any]) -> Any:
    """Use HA's actual template engine for nested case and report values."""
    if isinstance(value, str) and ("{{" in value or "{%" in value):
        return Template(value, hass).async_render(context)
    if isinstance(value, list):
        return [_render(hass, child, context) for child in value]
    if isinstance(value, dict):
        return {key: _render(hass, child, context) for key, child in value.items()}
    return value


def _case_variables(example: dict[str, Any]) -> dict[str, Any]:
    return next(
        step["variables"]
        for step in example["sequence"]
        if "test_cases" in step.get("variables", {})
    )


async def test_example_matches_home_assistant_script_schema(
    hass: HomeAssistant, example: dict[str, Any]
) -> None:
    validated = SCRIPT_ENTITY_SCHEMA(deepcopy(example))
    assert validated["mode"] == "single"
    assert "script" not in example  # UI script, not a scripts.yaml wrapper.
    assert example["fields"]["test_directory"]["default"] == "/config/pdf-test"
    assert example["fields"]["include_extract_pages"]["default"] is True
    assert example["fields"]["reported_version"]["default"] == ""
    assert not re.search(r"\b\d+\.\d+\.\d+", example["alias"])


@pytest.mark.parametrize("extract_enabled", [True, False])
async def test_example_cases_are_safe_and_counts_match_enabled_features(
    hass: HomeAssistant, example: dict[str, Any], extract_enabled: bool
) -> None:
    prefix = "/config/pdf-test/stirling_test_fixture"
    context = {
        "directory": "/config/pdf-test",
        "prefix": prefix,
        "run_id": "fixture",
        "extract_enabled": extract_enabled,
    }
    cases = _render(hass, _case_variables(example)["test_cases"], context)
    assert len(cases) == 14
    active = [case for case in cases if case["available"]]
    assert sum(case["expect"] == "success" for case in active) == (
        6 if extract_enabled else 5
    )
    assert sum(case["expect"] == "rejection" for case in active) == (
        8 if extract_enabled else 6
    )
    assert all(isinstance(case["available"], bool) for case in cases)
    overwrite_cases = [case for case in cases if case["data"]["overwrite"]]
    assert len(overwrite_cases) == 1
    assert overwrite_cases[0]["requires"] == "compress"
    assert overwrite_cases[0]["data"]["output_path"] == f"{prefix}_compressed.pdf"
    for case in cases:
        output = case["data"]["output_path"]
        assert output not in ("/config/pdf-test/a.pdf", "/config/pdf-test/b.pdf")
        if output.startswith("/stirling_pdf_test_"):
            assert case["expect"] == "rejection"
        else:
            assert output.startswith(prefix)
    extraction = [case for case in cases if case["operation"] == "extract_pages"]
    assert len(extraction) == 3
    assert all(case["available"] is extract_enabled for case in extraction)
    assert extraction[0]["data"]["page_numbers"] == "1"
    assert extraction[0]["data"]["output_path"] == f"{prefix}_extracted.pdf"


@pytest.mark.parametrize("extract_enabled", [True, False])
async def test_example_summary_renders_with_ha_and_retains_manual_check_warnings(
    hass: HomeAssistant, example: dict[str, Any], extract_enabled: bool
) -> None:
    context = {
        "directory": "/config/pdf-test",
        "prefix": "/config/pdf-test/stirling_test_fixture",
        "run_id": "fixture",
        "extract_enabled": extract_enabled,
        "reported_version": "",
        "deployment_label": "synthetic test environment",
        "jobs_entity": "sensor.example_jobs",
        "last_entity": "sensor.example_operation",
        "reachable_entity": "binary_sensor.example_reachable",
        "start_count": 0,
    }
    cases = _render(hass, _case_variables(example)["test_cases"], context)
    context["test_cases"] = cases
    count_step = next(
        step["variables"]
        for step in example["sequence"]
        if "expected_successes" in step.get("variables", {})
    )
    context.update(_render(hass, count_step, context))
    results = []
    count = 0
    for case in cases:
        if not case["available"]:
            results.append(
                {"name": case["name"], "status": "UEBERSPRUNGEN", "detail": "disabled"}
            )
            continue
        before = count
        success = case["expect"] == "success"
        count += int(success)
        results.append(
            {
                "name": case["name"],
                "status": "OK" if success else "ABGEWIESEN",
                "before": before,
                "after": count,
                "size": 100 if success else 0,
                "expected": case.get("expected_error", ""),
            }
        )
    context["results"] = results
    hass.states.async_set(context["jobs_entity"], str(count))
    hass.states.async_set(
        context["last_entity"],
        "extract_pages" if extract_enabled else "compress",
        {"last_run": "2026-01-01T00:00:00+00:00"},
    )
    hass.states.async_set(context["reachable_entity"], "on")
    report = _render(hass, example["sequence"][-1]["data"]["message"], context)
    expected_rejections = 8 if extract_enabled else 6
    assert f"**Erfolgreich:** {count} / {count}" in report
    assert (
        "**Abgewiesen, Fehlergrund noch im Trace pruefen:** "
        f"{expected_rejections} / {expected_rejections}" in report
    )
    assert "**Fehler:** 0" in report
    assert "**Installierte Integrationsversion:** nicht automatisch geprueft." in report
    assert "keine automatische Merge-Freigabe" in report


def test_issue_form_distinguishes_versions_deployments_and_authentication() -> None:
    form = yaml.safe_load(
        (ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml").read_text("utf-8")
    )
    fields = {field["id"]: field for field in form["body"] if "id" in field}
    assert fields["integration_version"]["validations"]["required"] is True
    assert fields["stirling_pdf_version"]["validations"]["required"] is True
    assert fields["server_installation"]["validations"]["required"] is True
    assert (
        "Home Assistant Community App"
        in fields["server_installation"]["attributes"]["options"]
    )
    options = fields["authentication"]["attributes"]["options"]
    assert "HTTP Basic username/password only" in options
    assert "HTTP Basic and Stirling PDF API key" in options
    assert "community_app_version" in fields
