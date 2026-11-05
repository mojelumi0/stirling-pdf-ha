"""Validate the standalone custom-integration project files."""

from __future__ import annotations

import ast
import json
import re
import struct
from pathlib import Path
from typing import Any

import yaml
from homeassistant.helpers.selector import selector as selector_factory

from custom_components.stirling_pdf.const import SERVICES
from custom_components.stirling_pdf.operations import OPERATIONS
from custom_components.stirling_pdf.tools import ha_field_name, tool_schema

ROOT = Path(__file__).resolve().parents[3]
INTEGRATION = ROOT / "custom_components" / "stirling_pdf"
WORKFLOWS = ROOT / ".github" / "workflows"


def _png_dimensions_and_color_type(path: Path) -> tuple[int, int, int]:
    """Return the dimensions and PNG color type from the IHDR chunk."""
    content = path.read_bytes()
    assert content.startswith(b"\x89PNG\r\n\x1a\n")
    assert content[12:16] == b"IHDR"
    width, height = struct.unpack(">II", content[16:24])
    return width, height, content[25]


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
    assert manifest["categories"] == ["productivity_information.documents_photos"]
    assert manifest["config_flow"] is True
    assert manifest["single_config_entry"] is False
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

    assert set(services) == set(SERVICES)
    assert set(strings["services"]) == set(services)
    assert set(english["services"]) == set(services)
    assert set(german["services"]) == set(services)
    for service, description in services.items():
        field_keys = set(description["fields"])
        assert re.fullmatch(r"[a-z0-9]+(?:[_-][a-z0-9]+)*", service), service
        for key in field_keys:
            assert re.fullmatch(r"[a-z0-9]+(?:[_-][a-z0-9]+)*", key), (service, key)
        assert set(strings["services"][service]["fields"]) == field_keys
        assert set(english["services"][service]["fields"]) == field_keys
        assert set(german["services"][service]["fields"]) == field_keys


def test_translation_structures_match() -> None:
    strings = _load_json(INTEGRATION / "strings.json")
    english = _load_json(INTEGRATION / "translations" / "en.json")
    german = _load_json(INTEGRATION / "translations" / "de.json")

    assert strings == english
    assert _nested_keys(english) == _nested_keys(german)


def test_action_selectors_accept_their_documented_defaults() -> None:
    services = yaml.safe_load((INTEGRATION / "services.yaml").read_text("utf-8"))
    for service in services.values():
        for field in service["fields"].values():
            selector = selector_factory(field["selector"])
            if "default" in field:
                selector(field["default"])


def test_catalog_public_fields_are_unique_and_match_service_schemas() -> None:
    services = yaml.safe_load((INTEGRATION / "services.yaml").read_text("utf-8"))
    for name, operation in OPERATIONS.items():
        public_names = [
            ha_field_name(api_name)
            for api_name in [*operation["fields"], *operation["files"]]
        ]
        reserved = {
            "config_entry_id",
            "output_path",
            "overwrite",
            "file_path",
            "file_paths",
        }
        assert len(public_names) == len(set(public_names)), name
        assert not (reserved & set(public_names)), name
        schema_keys = {key.schema for key in tool_schema(operation).schema}
        assert schema_keys == set(services[name]["fields"]), name


def test_hacs_manifest_is_valid() -> None:
    hacs = _load_json(ROOT / "hacs.json")

    assert hacs == {
        "name": "Stirling PDF",
        "homeassistant": "2026.9.0",
    }


def test_brand_icons_have_supported_sizes_and_transparency() -> None:
    """Validate the local Home Assistant and HACS brand assets."""
    brand = INTEGRATION / "brand"

    for filename, expected_size in (("icon.png", 256), ("icon@2x.png", 512)):
        width, height, color_type = _png_dimensions_and_color_type(brand / filename)
        assert (width, height) == (expected_size, expected_size)
        assert color_type in {4, 6}


def test_integration_package_contains_runtime_files() -> None:
    """Ensure source archives contain every runtime file required by HACS."""
    expected_files = {
        "__init__.py",
        "api.py",
        "binary_sensor.py",
        "config_flow.py",
        "const.py",
        "coordinator.py",
        "diagnostics.py",
        "entity.py",
        "manifest.json",
        "sensor.py",
        "metrics.py",
        "operations.py",
        "tools.py",
        "services.yaml",
        "strings.json",
        "brand/icon.png",
        "brand/icon@2x.png",
        "translations/de.json",
        "translations/en.json",
    }

    for relative_path in expected_files:
        assert (INTEGRATION / relative_path).is_file()


def test_github_validation_workflows_exist() -> None:
    workflow_names = {
        "tests.yml",
        "hassfest.yml",
        "validate.yaml",
        "release-drafter.yml",
        "release-version-check.yml",
        "server-tests.yml",
        "ha-2026-11.yml",
    }

    for name in workflow_names:
        workflow = (WORKFLOWS / name).read_text(encoding="utf-8")
        parsed = yaml.safe_load(workflow)
        assert isinstance(parsed, dict)
        assert "jobs" in parsed

    tests_workflow = (WORKFLOWS / "tests.yml").read_text(encoding="utf-8")
    assert 'python-version: "3.14"' in tests_workflow
    assert "python -m pytest" in tests_workflow
    assert "--cov=custom_components/stirling_pdf" in tests_workflow
    assert "--cov-fail-under=95" in tests_workflow
    assert "--cov-report=json:coverage.json" in tests_workflow
    assert "python scripts/check_coverage.py coverage.json" in tests_workflow
    assert (ROOT / "scripts" / "check_coverage.py").is_file()
    assert "ruff check" in tests_workflow
    assert "ruff format --check" in tests_workflow

    hassfest_workflow = (WORKFLOWS / "hassfest.yml").read_text(encoding="utf-8")
    assert "home-assistant/actions/hassfest@master" in hassfest_workflow

    hacs_workflow = (WORKFLOWS / "validate.yaml").read_text(encoding="utf-8")
    assert "hacs/action@main" in hacs_workflow
    assert "category: integration" in hacs_workflow

    release_drafter_workflow = (WORKFLOWS / "release-drafter.yml").read_text(
        encoding="utf-8"
    )
    assert "release-drafter/release-drafter@v7" in release_drafter_workflow

    release_version_workflow = (WORKFLOWS / "release-version-check.yml").read_text(
        encoding="utf-8"
    )
    assert "github.event.release.tag_name" in release_version_workflow
    assert "custom_components/stirling_pdf/manifest.json" in release_version_workflow


def test_manual_2026_11_workflow_keeps_dependency_and_coverage_checks() -> None:
    """Do not confuse a prepared manual job with automatic compatibility proof."""
    workflow = (WORKFLOWS / "ha-2026-11.yml").read_text(encoding="utf-8")
    parsed = yaml.safe_load(workflow)
    # PyYAML's YAML 1.1 loader treats the unquoted workflow key `on` as True.
    triggers = parsed.get("on", parsed.get(True))
    assert set(triggers) == {"workflow_dispatch"}
    version_input = triggers["workflow_dispatch"]["inputs"]["test_plugin_version"]
    assert version_input["required"] is True
    assert "default" not in version_input
    job = parsed["jobs"]["compatibility"]
    assert job["env"]["EXPECTED_HA_VERSION"] == "2026.11.0"
    assert "continue-on-error" not in job
    commands = "\n".join(step.get("run", "") for step in job["steps"])
    assert '"homeassistant==$EXPECTED_HA_VERSION"' in commands
    assert (
        '"pytest-homeassistant-custom-component==$HA_TEST_PLUGIN_VERSION"' in commands
    )
    assert "-r requirements-dev-common.txt" in commands
    assert "python -m pip check" in commands
    assert "--no-deps" not in commands
    assert "--override" not in commands
    assert "--cov-fail-under=95" in commands
    assert "python scripts/check_coverage.py coverage.json" in commands
    assert all("continue-on-error" not in step for step in job["steps"])


def test_server_matrix_pins_both_versions_and_login_modes() -> None:
    """A green old-server job is not compatibility evidence for the new release."""
    workflow = yaml.safe_load((WORKFLOWS / "server-tests.yml").read_text("utf-8"))
    job = workflow["jobs"]["server"]
    matrix = job["strategy"]["matrix"]
    assert matrix["version"] == ["3.2.0", "3.3.0"]
    assert matrix["login"] == ["true", "false"]
    images = {row["version"]: row["image"] for row in matrix["include"]}
    assert set(images) == set(matrix["version"])
    for version, image in images.items():
        assert re.fullmatch(
            r"stirlingtools/stirling-pdf:"
            + re.escape(version)
            + r"@sha256:[a-f0-9]{64}",
            image,
        )
    assert images["3.2.0"].endswith(
        "10164ffe04961b02ebc9fa4da12064eeacb8d3bc3e09ceb059f78ce7aaa83207"
    )
    assert job["services"]["stirling"]["image"] == "${{ matrix.image }}"
    step = next(step for step in job["steps"] if "tests_live" in step.get("run", ""))
    assert step["env"]["STIRLING_PDF_EXPECTED_VERSION"] == "${{ matrix.version }}"
    assert "continue-on-error" not in job


def test_330_contract_metadata_and_converter_defaults_are_explicit() -> None:
    assert OPERATIONS["replace_text"]["removed_in"] == [3, 3, 0]
    newer = {
        name
        for name, operation in OPERATIONS.items()
        if "office_convert_since" in operation
    }
    assert newer == {
        "pdf_to_pdfa",
        "pdf_to_xml",
        "html_to_pdf",
        "markdown_to_pdf",
        "pdf_to_html",
        "pdf_to_markdown",
        "eml_to_pdf",
        "ebook_to_pdf",
        "pdf_to_epub",
    }
    services = yaml.safe_load((INTEGRATION / "services.yaml").read_text("utf-8"))
    converters = 0
    for name, operation in OPERATIONS.items():
        field = operation["fields"].get("useStirlingOfficeConvert")
        if field is not None:
            converters += 1
            assert field["default"] is False
            assert (
                services[name]["fields"]["use_stirling_office_convert"]["default"]
                is False
            )
        if name in newer:
            assert operation["office_convert_since"] == [3, 3, 0]
    assert converters == 14


def test_config_forms_always_supply_an_explicit_step_id() -> None:
    """Keep setup, reconfigure, reauth and options compatible with new HA flows."""
    tree = ast.parse((INTEGRATION / "config_flow.py").read_text(encoding="utf-8"))
    forms = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr
        in {
            "async_show_form",
            "async_show_menu",
            "async_show_progress",
            "async_external_step",
        }
    ]
    assert forms
    for form in forms:
        assert any(keyword.arg == "step_id" for keyword in form.keywords)


def test_marketplace_documentation_preserves_older_ha_support() -> None:
    """Document migration without implying catalog acceptance or newer minimum HA."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Settings > Marketplace" in readme
    assert "hacs_repository/?owner=mojelumi0" in readme
    assert "### HACS (Home Assistant before 2026.11)" in readme
    assert (ROOT / "docs" / "HA_2026_11.md").is_file()
    bug_report = yaml.safe_load(
        (ROOT / ".github/ISSUE_TEMPLATE/bug_report.yml").read_text("utf-8")
    )
    installation = next(
        item for item in bug_report["body"] if item.get("id") == "installation"
    )
    assert installation["attributes"]["options"][:2] == [
        "Marketplace (Home Assistant 2026.11 or newer)",
        "HACS (Home Assistant before 2026.11)",
    ]


def test_release_drafter_config_exists() -> None:
    config = (ROOT / ".github" / "release-drafter.yml").read_text(encoding="utf-8")
    parsed = yaml.safe_load(config)

    assert isinstance(parsed, dict)
    assert parsed["tag-template"] == "$RESOLVED_VERSION"
    assert parsed["include-pre-releases"] is True
    assert "$CHANGES" in parsed["template"]


def test_community_health_files_exist() -> None:
    for filename in ("bug_report.yml", "feature_request.yml", "config.yml"):
        path = ROOT / ".github" / "ISSUE_TEMPLATE" / filename
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(parsed, dict)

    assert "Local checks" in (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "Reporting a vulnerability" in (ROOT / "SECURITY.md").read_text(
        encoding="utf-8"
    )
