"""Enforce line coverage per integration module, without rounded comparisons."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = Path("custom_components/stirling_pdf")


@dataclass(frozen=True)
class ModuleCoverage:
    """One module's result, including missing coverage records."""

    name: str
    covered: int
    statements: int
    missing: tuple[int, ...] = ()
    error: str | None = None

    @property
    def target(self) -> str:
        """Describe the stricter config-flow rule separately."""
        return "100%" if self.name == "config_flow.py" else ">95%"

    @property
    def passed(self) -> bool:
        """Use integer counts: exactly 95% is not more than 95%."""
        if self.error:
            return False
        if self.name == "config_flow.py":
            return self.covered == self.statements
        return self.statements == 0 or self.covered * 100 > self.statements * 95

    @property
    def percentage(self) -> float:
        """Return a percentage for display only, never for pass/fail decisions."""
        return 100 * self.covered / self.statements if self.statements else 100.0


def evaluate_report(report: Any, root: Path) -> list[ModuleCoverage]:
    """Require a valid record for every Python module in the source directory."""
    if not isinstance(report, dict) or not isinstance(report.get("files"), dict):
        raise ValueError("Coverage JSON must contain a 'files' object")
    source = root / INTEGRATION
    expected = sorted(source.rglob("*.py"))
    if not expected or not (source / "config_flow.py").is_file():
        raise ValueError("Integration sources or config_flow.py are missing")
    records = {}
    for name, record in report["files"].items():
        path = Path(name.replace("\\", "/"))
        resolved = (path if path.is_absolute() else root / path).resolve()
        if resolved in records:
            raise ValueError(f"Duplicate coverage record: {name}")
        records[resolved] = record
    results = []
    for path in expected:
        name = path.relative_to(source).as_posix()
        record = records.get(path.resolve())
        if record is None:
            results.append(ModuleCoverage(name, 0, 0, error="Missing coverage record"))
            continue
        try:
            summary = record["summary"]
            covered = summary["covered_lines"]
            statements = summary["num_statements"]
            missing = record["missing_lines"]
            if (
                type(covered) is not int
                or type(statements) is not int
                or not 0 <= covered <= statements
                or not isinstance(missing, list)
                or any(type(line) is not int or line <= 0 for line in missing)
                or len(set(missing)) != len(missing)
                or len(missing) != statements - covered
            ):
                raise ValueError("Inconsistent line counts")
        except (KeyError, TypeError, ValueError) as err:
            raise ValueError(f"Invalid coverage record for {name}: {err}") from err
        results.append(ModuleCoverage(name, covered, statements, tuple(missing)))
    return results


def format_summary(results: list[ModuleCoverage]) -> str:
    """Create a console and GitHub job-summary table from the same results."""
    rows = [
        "## Integration line coverage",
        "",
        "| Module | Covered / statements | Coverage | Required | Result |",
        "|---|---:|---:|---:|---|",
    ]
    notes = []
    for result in results:
        coverage = f"{result.percentage:.2f}%" if not result.error else "n/a"
        outcome = "PASS" if result.passed else "FAIL"
        rows.append(
            f"| `{result.name}` | {result.covered} / {result.statements} | "
            f"{coverage} | {result.target} | {outcome} |"
        )
        if result.error:
            notes.append(f"- `{result.name}`: {result.error}")
        elif result.missing:
            notes.append(
                f"- `{result.name}` missing lines: "
                + ", ".join(map(str, result.missing))
            )
    if notes:
        rows.extend(["", *notes])
    rows.extend(["", "Targets use exact line counts, not rounded percentages."])
    return "\n".join(rows) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Read the pytest-cov JSON report and return a failing CI exit code if needed."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, nargs="?", default=Path("coverage.json"))
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        results = evaluate_report(report, ROOT)
    except (OSError, ValueError) as err:
        print(f"Coverage check failed: {err}", file=sys.stderr)
        return 1
    summary = format_summary(results)
    print(summary)
    if summary_path := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary_path).open("a", encoding="utf-8") as output:
            output.write(summary)
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
