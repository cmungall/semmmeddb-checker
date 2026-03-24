#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from linkml_reference_validator.models import ReferenceValidationConfig
from linkml_reference_validator.validation.supporting_text_validator import SupportingTextValidator

from review_data import build_review_bundle, get_ncbi_email


def validator_ready_snippet(snippet: str) -> str:
    prepared = re.sub(r"\[[^\]]+\]", "...", snippet)
    prepared = re.sub(r"\.\.\.(?:\s*\.\.\.)+", "...", prepared)
    return re.sub(r"\s+", " ", prepared).strip()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    report_path = root / "data" / "snippet_validation_report.json"

    bundle = build_review_bundle(root).bundle
    validator = SupportingTextValidator(
        ReferenceValidationConfig(
            cache_dir=root / "references_cache",
            email=get_ncbi_email(),
            rate_limit_delay=0.0,
        )
    )

    results: list[dict[str, object]] = []
    title_checks = 0
    snippet_checks = 0
    invalid_count = 0

    for pmid, payload in sorted(bundle.items(), key=lambda item: int(item[0])):
        reference_id = f"PMID:{pmid}"
        title = payload.get("title", "")
        if title:
            title_result = validator.validate_title(reference_id, title, path=f"{pmid}.title")
            title_checks += 1
            results.append(
                {
                    "kind": "title",
                    "path": f"{pmid}.title",
                    "reference_id": reference_id,
                    "is_valid": title_result.is_valid,
                    "message": title_result.message,
                }
            )
            if not title_result.is_valid:
                invalid_count += 1

        for row_index, row in enumerate(payload["rows"]):
            for snippet_index, snippet in enumerate(row.get("supporting_snippets", [])):
                prepared_snippet = validator_ready_snippet(snippet)
                validation = validator.validate(
                    prepared_snippet,
                    reference_id,
                    path=f"{pmid}.rows[{row_index}].supporting_snippets[{snippet_index}]",
                )
                snippet_checks += 1
                results.append(
                    {
                        "kind": "snippet",
                        "path": f"{pmid}.rows[{row_index}].supporting_snippets[{snippet_index}]",
                        "reference_id": reference_id,
                        "subject": row["source_row"]["subject"],
                        "predicate": row["source_row"]["predicate"],
                        "object": row["source_row"]["object"],
                        "snippet": snippet,
                        "validator_snippet": prepared_snippet,
                        "is_valid": validation.is_valid,
                        "message": validation.message,
                    }
                )
                if not validation.is_valid:
                    invalid_count += 1

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "title_checks": title_checks,
            "snippet_checks": snippet_checks,
            "invalid_count": invalid_count,
        },
        "results": results,
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        f"Validated {title_checks} titles and {snippet_checks} snippets; "
        f"invalid checks: {invalid_count}"
    )
    if invalid_count:
        print(f"See {report_path} for details.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
