"""Render repository badges from the same source-bound reports used by CI."""

import json
import sys
from html import escape
from pathlib import Path

from check_coverage import check
from coverage_provenance import report_path


def render(root, output, revision):
    root, output = Path(root), Path(output)
    reports = {}
    for scope in ("backend", "frontend"):
        check(scope, root / scope)
        report = json.loads(report_path(scope, root / scope).read_text())
        if scope == "backend":
            totals = report["totals"]
            metrics = {
                "lines": [totals["covered_lines"], totals["num_statements"]],
                "branches": [totals["covered_branches"], totals["num_branches"]],
            }
        else:
            metrics = {
                key: [report["total"][key]["covered"], report["total"][key]["total"]]
                for key in ("lines", "branches")
            }
        reports[scope] = metrics
    # Validate both reports before writing any badge.
    output.mkdir(parents=True, exist_ok=True)
    for scope, metrics in reports.items():
        values = [
            f"{name} {covered / total:.0%}" if total else f"{name} n/a"
            for name, (covered, total) in metrics.items()
        ]
        label = f"{scope} coverage"
        message = " | ".join(values)
        title = escape(f"{label}: {message}")
        (output / f"{scope}.svg").write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="326" height="20" '
            f'role="img" aria-label="{title}">\n'
            f'<title>{title}</title>\n'
            '<rect width="326" height="20" rx="3" fill="#555"/>\n'
            '<path fill="#237b32" d="M126 0h197q3 0 3 3v14q0 3-3 3H126z"/>\n'
            '<g fill="#fff" text-anchor="middle" font-family="Verdana,DejaVu Sans,sans-serif" font-size="11">\n'
            f'<text x="63" y="14">{label}</text>\n'
            f'<text x="226" y="14">{message}</text>\n'
            '</g>\n</svg>\n'
        )
    (output / "coverage.json").write_text(
        json.dumps({"revision": revision, "coverage": reports}, indent=2) + "\n"
    )


if __name__ == "__main__":
    render(*sys.argv[1:])
