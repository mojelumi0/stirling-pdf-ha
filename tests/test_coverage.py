"""Test the per-module coverage gate with synthetic reports, not fixed versions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import check_coverage


def _record(covered: int, statements: int) -> dict:
    return {
        "summary": {"covered_lines": covered, "num_statements": statements},
        "missing_lines": list(range(covered + 1, statements + 1)),
    }


@pytest.fixture
def report_root(tmp_path: Path) -> Path:
    """Create only disposable, synthetic source files for the checker."""
    source = tmp_path / check_coverage.INTEGRATION
    source.mkdir(parents=True)
    for name in ("config_flow.py", "api.py"):
        (source / name).write_text("# synthetic source\n", encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    ("module", "covered", "statements", "passed"),
    [
        ("api.py", 95, 100, False),
        ("api.py", 96, 100, True),
        ("api.py", 9501, 10000, True),
        ("api.py", 0, 0, True),
        ("config_flow.py", 9999, 10000, False),
        ("config_flow.py", 100, 100, True),
    ],
)
def test_thresholds_use_exact_counts(
    module: str, covered: int, statements: int, passed: bool
) -> None:
    result = check_coverage.ModuleCoverage(module, covered, statements)
    assert result.passed is passed


def test_missing_module_cannot_be_hidden_by_a_high_total(report_root: Path) -> None:
    report = {
        "files": {"custom_components/stirling_pdf/config_flow.py": _record(100, 100)}
    }
    results = check_coverage.evaluate_report(report, report_root)
    assert len(results) == 2
    assert not results[0].passed
    assert results[0].error == "Missing coverage record"
    assert results[1].passed
    assert "n/a" in check_coverage.format_summary(results)


def test_relative_and_absolute_report_paths(report_root: Path) -> None:
    report = {
        "files": {
            "custom_components\\stirling_pdf\\api.py": _record(96, 100),
            str(report_root / check_coverage.INTEGRATION / "config_flow.py"): _record(
                100, 100
            ),
        }
    }
    results = check_coverage.evaluate_report(report, report_root)
    assert all(result.passed for result in results)
    summary = check_coverage.format_summary(results)
    assert "api.py" in summary
    assert ">95%" in summary
    assert "100%" in summary
    assert "missing lines: 97, 98, 99, 100" in summary


@pytest.mark.parametrize("report", [None, {}, {"files": []}])
def test_invalid_report_is_rejected(report_root: Path, report: object) -> None:
    with pytest.raises(ValueError, match="files"):
        check_coverage.evaluate_report(report, report_root)


@pytest.mark.parametrize(
    "record",
    [
        {},
        _record(101, 100),
        _record(-1, 100),
        {"summary": {"covered_lines": True, "num_statements": 1}, "missing_lines": []},
        {"summary": {"covered_lines": 1, "num_statements": 2}, "missing_lines": []},
    ],
)
def test_inconsistent_counts_are_rejected(report_root: Path, record: dict) -> None:
    with pytest.raises(ValueError, match="Invalid coverage record"):
        check_coverage.evaluate_report(
            {"files": {"custom_components/stirling_pdf/api.py": record}}, report_root
        )


def test_missing_sources_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="sources"):
        check_coverage.evaluate_report({"files": {}}, tmp_path)


def test_new_source_module_is_automatically_required(report_root: Path) -> None:
    """Do not let a future module bypass the gate through a hardcoded file list."""
    (report_root / check_coverage.INTEGRATION / "new_module.py").write_text(
        "# synthetic source\n", encoding="utf-8"
    )
    report = {
        "files": {
            "custom_components/stirling_pdf/api.py": _record(100, 100),
            "custom_components/stirling_pdf/config_flow.py": _record(100, 100),
        }
    }
    results = check_coverage.evaluate_report(report, report_root)
    assert len(results) == 3
    assert not results[-1].passed
    assert results[-1].name == "new_module.py"


def test_duplicate_normalized_paths_are_rejected(report_root: Path) -> None:
    """A second spelling of the same path must not silently replace a result."""
    report = {
        "files": {
            "custom_components/stirling_pdf/config_flow.py": _record(100, 100),
            str(report_root / check_coverage.INTEGRATION / "config_flow.py"): _record(
                99, 100
            ),
        }
    }
    with pytest.raises(ValueError, match="Duplicate coverage record"):
        check_coverage.evaluate_report(report, report_root)


@pytest.mark.parametrize("covered", [95, 96])
def test_cli_exit_code_and_job_summary(
    report_root: Path, monkeypatch: pytest.MonkeyPatch, covered: int
) -> None:
    report = {
        "files": {
            "custom_components/stirling_pdf/api.py": _record(covered, 100),
            "custom_components/stirling_pdf/config_flow.py": _record(100, 100),
        }
    }
    report_path = report_root / "coverage.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    summary_path = report_root / "summary.md"
    monkeypatch.setattr(check_coverage, "ROOT", report_root)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))
    assert check_coverage.main([str(report_path)]) == (0 if covered > 95 else 1)
    summary = summary_path.read_text(encoding="utf-8")
    assert "Integration line coverage" in summary
    assert ("FAIL" in summary) is (covered == 95)


@pytest.mark.parametrize("body", [None, "not JSON", "{}"])
def test_cli_rejects_missing_or_malformed_report(
    tmp_path: Path, capsys: pytest.CaptureFixture, body: str | None
) -> None:
    report = tmp_path / "missing.json"
    if body is not None:
        report.write_text(body, encoding="utf-8")
    assert check_coverage.main([str(report)]) == 1
    assert "Coverage check failed" in capsys.readouterr().err
