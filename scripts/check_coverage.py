"""Fail closed on raw independent coverage counts and missing source files."""
import json
import sys
from pathlib import Path


def require_metric(covered, total):
    if type(covered) is not int or type(total) is not int:
        raise ValueError("Coverage counts must be integers")
    if not 0 <= covered <= total or (total and 100 * covered < 90 * total):
        raise ValueError(f"Coverage below 90% or invalid: {covered}/{total}")


def check(scope, root):
    root = Path(root)
    if scope == "backend":
        report = json.loads((root / "coverage/coverage.json").read_text())
        expected = {str(p.relative_to(root)) for p in (root / "app").rglob("*.py")}
        if set(report["files"]) != expected:
            raise ValueError("Backend source/report mismatch")
        summary = report["totals"]
        metrics = [(summary["covered_lines"], summary["num_statements"]),
                   (summary["covered_branches"], summary["num_branches"])]
    elif scope == "frontend":
        report = json.loads((root / "coverage/coverage-summary.json").read_text())
        expected = {str(p.relative_to(root)) for p in (root / "src").rglob("*") if p.suffix in {".ts", ".tsx"}}
        actual = {"src/" + p.split("/src/", 1)[1] for p in report if p != "total"}
        if actual != expected:
            raise ValueError("Frontend source/report mismatch")
        metrics = [(report["total"][key]["covered"], report["total"][key]["total"]) for key in ("lines", "branches")]
    else:
        raise ValueError("Unknown scope")
    if not expected or metrics[0][1] <= 0:
        raise ValueError("Empty source/line coverage")
    for label, (covered, total) in zip(("lines", "branches"), metrics):
        require_metric(covered, total)
        print(f"{scope} {label}: {covered}/{total}")


if __name__ == "__main__":
    check(sys.argv[1], sys.argv[2])
