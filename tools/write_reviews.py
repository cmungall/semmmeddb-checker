#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path


def render_review(pmid: str, payload: dict) -> str:
    lines = [
        f"# PMID {pmid}",
        "",
        f"Title: {payload['title']}",
        "",
        "What the abstract does say:",
        payload["summary"],
        "",
        "Assertions:",
    ]
    for row in payload["rows"]:
        lines.extend(
            [
                f"- `{row['subject']}` -> `{row['predicate']}` -> `{row['object']}`",
                f"  Dataset call: `{row['dataset_call']}`",
                f"  My assessment: `{row['assessment']}`",
                f"  Why: {row['reason']}",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    root = Path(".").resolve()
    assessments_path = root / "data" / "manual_assessments.json"
    outdir = root / "reviews"
    outdir.mkdir(exist_ok=True)

    assessments = json.loads(assessments_path.read_text())
    for pmid, payload in sorted(assessments.items(), key=lambda x: int(x[0])):
        (outdir / f"{pmid}.md").write_text(render_review(pmid, payload))


if __name__ == "__main__":
    main()
