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
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import entity_sources
from homeassistant.helpers.script_variables import ScriptVariables
from homeassistant.helpers.template import Template
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stirling_pdf.const import DOMAIN
from custom_components.stirling_pdf.operations import OPERATIONS
from custom_components.stirling_pdf.tools import tool_schema

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


def _render_initial_variables(hass, script, inputs):
    """Render the real first-step variables sequentially using HA globals."""
    values = {
        name: Template(value, hass)
        if isinstance(value, str) and ("{{" in value or "{%" in value)
        else deepcopy(value)
        for name, value in script["sequence"][0]["variables"].items()
    }
    return ScriptVariables(values).async_render(hass, inputs)


def _discovery_entry(hass: HomeAssistant, domain: str, label: str):
    """Register realistic sensors without loading or contacting a backend."""
    entry = MockConfigEntry(domain=domain, title="Same friendly server name", data={})
    entry.add_to_hass(hass)
    entities = {}
    for platform, suffix, state, attributes in [
        ("sensor", "jobs", "4", {"state_class": "total_increasing"}),
        ("sensor", "last", "merge", {"device_class": "enum"}),
        ("binary_sensor", "reachable", "on", {"device_class": "connectivity"}),
        ("sensor", "optional", "17", {"state_class": "measurement"}),
    ]:
        registered = er.async_get(hass).async_get_or_create(
            platform,
            domain,
            f"{entry.entry_id}_{suffix}",
            config_entry=entry,
            suggested_object_id=f"fixture_{label}_{suffix}",
        )
        entities[suffix] = registered.entity_id
        entity_sources(hass)[registered.entity_id] = {
            "domain": domain,
            "config_entry": entry.entry_id,
        }
        hass.states.async_set(registered.entity_id, state, attributes)
    return entry, entities


@pytest.mark.parametrize("filename", ["ha_test.yaml", "ha_tools_test.yaml"])
@pytest.mark.parametrize("selected_index", [0, 1])
async def test_initial_discovery_uses_real_ha_functions_and_exact_entry_ids(
    hass: HomeAssistant, filename: str, selected_index: int
) -> None:
    script = yaml.safe_load((ROOT / "examples" / filename).read_text("utf-8"))
    first = _discovery_entry(hass, DOMAIN, "first")
    second = _discovery_entry(hass, DOMAIN, "second")
    foreign = _discovery_entry(hass, "mqtt", "foreign")
    entry, entities = (first, second)[selected_index]
    values = _render_initial_variables(
        hass,
        script,
        {"config_entry_id": entry.entry_id, "test_directory": "/config/pdf-test"},
    )
    assert values["selected_server"] == entry.entry_id
    assert set(values["selected_entities"]) == set(entities.values())
    assert not (set(values["selected_entities"]) & set(foreign[1].values()))
    assert values["jobs_candidates"] == [entities["jobs"]]
    if filename == "ha_test.yaml":
        assert values["last_candidates"] == [entities["last"]]
        assert values["reachable_candidates"] == [entities["reachable"]]
    assert not _render(hass, script["sequence"][1]["if"], values)
    assert "config_entry_entities" not in (ROOT / "examples" / filename).read_text(
        "utf-8"
    )


@pytest.mark.parametrize("filename", ["ha_test.yaml", "ha_tools_test.yaml"])
@pytest.mark.parametrize("selection", ["missing", "foreign"])
async def test_invalid_selected_entry_stops_before_any_pdf_action(
    hass: HomeAssistant, filename: str, selection: str
) -> None:
    script = yaml.safe_load((ROOT / "examples" / filename).read_text("utf-8"))
    _discovery_entry(hass, DOMAIN, "first")
    foreign, _ = _discovery_entry(hass, "mqtt", "foreign")
    selected = "does-not-exist" if selection == "missing" else foreign.entry_id
    values = _render_initial_variables(hass, script, {"config_entry_id": selected})
    assert values["selected_entities"] == []
    assert values["jobs_candidates"] == []
    assert _render(hass, script["sequence"][1]["if"], values)


@pytest.mark.parametrize("server_count", [1, 2])
async def test_main_script_without_selection_retains_safe_single_server_fallback(
    hass: HomeAssistant, server_count: int
) -> None:
    script = yaml.safe_load((ROOT / "examples" / "ha_test.yaml").read_text("utf-8"))
    registered = [
        _discovery_entry(hass, DOMAIN, f"server_{i}") for i in range(server_count)
    ]
    values = _render_initial_variables(hass, script, {})
    # No input must not accidentally use HA's config_entry_id function as a value.
    assert values["selected_server"] == ""
    assert len(values["jobs_candidates"]) == server_count
    assert set(values["selected_entities"]) == {
        entity_id for _, entities in registered for entity_id in entities.values()
    }
    assert bool(_render(hass, script["sequence"][1]["if"], values)) is (
        server_count != 1
    )


async def test_additional_tools_without_selection_stop_safely(
    hass: HomeAssistant,
) -> None:
    script = yaml.safe_load(
        (ROOT / "examples" / "ha_tools_test.yaml").read_text("utf-8")
    )
    _discovery_entry(hass, DOMAIN, "first")
    values = _render_initial_variables(hass, script, {})
    assert values["selected_server"] == ""
    assert values["selected_entities"] == []
    assert _render(hass, script["sequence"][1]["if"], values)


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
    assert example["fields"]["config_entry_id"]["selector"] == {
        "config_entry": {"integration": "stirling_pdf"}
    }


async def test_extended_example_schema_and_safe_cases(hass: HomeAssistant) -> None:
    example = yaml.safe_load(
        (ROOT / "examples" / "ha_tools_test.yaml").read_text("utf-8")
    )
    SCRIPT_ENTITY_SCHEMA(deepcopy(example))
    assert example["fields"]["config_entry_id"]["required"] is True
    values = _case_variables(example)
    context = {
        "directory": "/config/pdf-test",
        "prefix": "/config/pdf-test/stirling_tools_fixture",
        "run_id": "fixture",
    }
    cases = _render(hass, values["test_cases"], context)
    assert len(cases) == 6
    assert {case["operation"] for case in cases} == {
        "rotate",
        "repair",
        "metadata",
        "watermark",
        "analyze_page_count",
        "check_contains_text",
    }
    for case in cases:
        assert case["data"]["file_path"] == "/config/pdf-test/a.pdf"
        tool_schema(OPERATIONS[case["operation"]])(
            {**case["data"], "config_entry_id": "selected-entry", "overwrite": False}
        )
        if "output_path" in case["data"]:
            assert case["data"]["output_path"].startswith(context["prefix"])
    action = next(step for step in example["sequence"] if "repeat" in step)["repeat"][
        "sequence"
    ][1]
    rendered = _render(
        hass,
        action["data"],
        {"repeat": {"item": cases[0]}, "selected_server": "selected-entry"},
    )
    assert rendered["config_entry_id"] == "selected-entry"
    assert rendered["overwrite"] is False


@pytest.mark.parametrize(
    ("filename", "title"),
    [
        ("ha_test.yaml", "Stirling PDF - Integration test"),
        ("ha_tools_test.yaml", "Stirling PDF - Additional tool test"),
    ],
)
def test_example_names_and_server_labels_are_english(filename: str, title: str) -> None:
    script = yaml.safe_load((ROOT / "examples" / filename).read_text("utf-8"))
    assert script["alias"] == title
    assert script["fields"]["config_entry_id"]["name"] == "Stirling PDF server"


@pytest.mark.parametrize(
    ("expect", "success", "rejected", "status"),
    [
        ("success", True, False, "OK"),
        ("rejection", False, True, "REJECTED"),
        ("success", False, False, "FAILED"),
        ("rejection", True, False, "FAILED"),
    ],
)
async def test_english_result_labels_keep_the_same_classification(
    hass: HomeAssistant,
    example: dict[str, Any],
    expect: str,
    success: bool,
    rejected: bool,
    status: str,
) -> None:
    loop = next(step["repeat"] for step in example["sequence"] if "repeat" in step)
    execute = loop["sequence"][0]["else"]
    values = next(
        step["variables"]
        for step in execute
        if "result_status" in step.get("variables", {})
    )
    assert (
        _render(
            hass,
            values["result_status"],
            {
                "repeat": {"item": {"expect": expect}},
                "success_observed": success,
                "rejection_observed": rejected,
            },
        )
        == status
    )


async def test_additional_tool_report_renders_english_safety_notes(
    hass: HomeAssistant,
) -> None:
    script = yaml.safe_load(
        (ROOT / "examples" / "ha_tools_test.yaml").read_text("utf-8")
    )
    context = {
        "directory": "/config/pdf-test",
        "prefix": "/config/pdf-test/stirling_tools_fixture",
        "run_id": "fixture",
        "selected_server": "selected-entry",
        "jobs_entity": "sensor.example_jobs",
        "start_count": 0,
    }
    cases = _render(hass, _case_variables(script)["test_cases"], context)
    context["test_cases"] = cases
    context["results"] = [
        {
            "operation": case["operation"],
            "ok": True,
            "before": index,
            "after": index + 1,
            "output": case["data"].get("output_path", ""),
        }
        for index, case in enumerate(cases)
    ]
    hass.states.async_set(context["jobs_entity"], "6")
    report = _render(hass, script["sequence"][-1]["data"]["message"], context)
    assert "**OK:** 6 / 6" in report
    assert "**Counter:** 0 -> 6" in report
    assert "not the entire catalog" in report
    assert "Do not rerun this script for persistence checks" in report
    assert "no automatic" in report


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
                {"name": case["name"], "status": "SKIPPED", "detail": "disabled"}
            )
            continue
        before = count
        success = case["expect"] == "success"
        count += int(success)
        results.append(
            {
                "name": case["name"],
                "status": "OK" if success else "REJECTED",
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
    assert f"**Successful:** {count} / {count}" in report
    assert (
        "**Rejected, check the reason in the trace:** "
        f"{expected_rejections} / {expected_rejections}" in report
    )
    assert "**Failed:** 0" in report
    assert "**Installed integration version:** not verified automatically." in report
    assert "not automatic merge approval" in report


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
