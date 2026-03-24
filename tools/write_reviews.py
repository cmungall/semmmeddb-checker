#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

from review_data import build_review_bundle, render_review


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    outdir = root / "reviews"
    outdir.mkdir(exist_ok=True)

    review_bundle = build_review_bundle(root).bundle
    for pmid, payload in sorted(review_bundle.items(), key=lambda x: int(x[0])):
        (outdir / f"{pmid}.md").write_text(render_review(pmid, payload))


if __name__ == "__main__":
    main()
