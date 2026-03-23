#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path


OBJECT_ALIASES = {
    "Tumor necrosis factor receptor superfamily, member 10a": [
        r"\bDR4\b",
        r"TRAIL-R1",
        r"death receptor(?:s)? 4",
        r"death receptor(?:s)? 4 and 5",
        r"TRAIL receptor 1",
        r"TRAIL",
    ],
    "Il2-inducible t-cell kinase": [
        r"\bITK\b",
        r"interleukin-2-inducible T-cell kinase",
        r"IL-2-inducible T-cell kinase",
    ],
    "dual specificity tyrosine phosphorylation regulated kinase 1A": [
        r"\bDYRK1A\b",
        r"dual-specificity tyrosine-phosphorylation-regulated kinase 1A",
    ],
    "diacylglycerol kinase beta": [
        r"\bDGK[ -]?beta\b",
        r"\bDGKβ\b",
        r"diacylglycerol kinase beta",
        r"DGK-B",
    ],
    "glucokinase": [
        r"\bglucokinase\b",
        r"\bGCK\b",
    ],
    "hexokinase 1": [
        r"\bhexokinase 1\b",
        r"\bHK1\b",
        r"\bhexokinase\b",
    ],
    "cyclin dependent kinase like 2": [
        r"\bCDKL2\b",
        r"cyclin-dependent kinase-like 2",
    ],
    "Deoxycytidine kinase": [
        r"\bdCK\b",
        r"deoxycytidine kinase",
    ],
    "death associated protein kinase 3": [
        r"\bDAPK3\b",
        r"\bZIPK\b",
        r"death-associated protein kinase 3",
    ],
    "death associated protein kinase 1": [
        r"\bDAPK1\b",
        r"death-associated protein kinase 1",
        r"\bDAP kinase\b",
    ],
    "Death-associated protein kinase 1": [
        r"\bDAPK1\b",
        r"death-associated protein kinase 1",
        r"\bDAP kinase\b",
    ],
    "CDC like kinase 1": [
        r"\bCLK1\b",
        r"Cdc-like kinase 1",
        r"CDC-like kinase 1",
    ],
    "Cdc-like kinase 1": [
        r"\bCLK1\b",
        r"Cdc-like kinase 1",
        r"CDC-like kinase 1",
    ],
    "transient receptor potential cation channel subfamily M member 6": [
        r"\bTRPM6\b",
        r"transient receptor potential melastatin 6",
    ],
    "aurora kinase B": [
        r"\bAur(?:ora)? ?B\b",
        r"\bAURKB\b",
        r"aurora kinase B",
    ],
    "Aurora kinase b": [
        r"\bAur(?:ora)? ?B\b",
        r"\bAURKB\b",
        r"aurora kinase B",
    ],
    "serine/threonine kinase 3": [
        r"\bMST2\b",
        r"serine/threonine kinase 3",
    ],
    "toll like receptor 1": [
        r"\bTLR1\b",
        r"toll-like receptor 1",
    ],
    "cyclin dependent kinase inhibitor 3": [
        r"\bCDKN3\b",
        r"cyclin-dependent kinase inhibitor 3",
    ],
    "checkpoint kinase 2": [
        r"\bCHEK2\b",
        r"\bCHK2\b",
        r"checkpoint kinase 2",
    ],
    "Cyclin-dependent kinase-like 3": [
        r"\bCDKL3\b",
        r"cyclin-dependent kinase-like 3",
    ],
}


KEYWORD_PATTERNS = [
    r"up-?regulat",
    r"down-?regulat",
    r"increas",
    r"decreas",
    r"induc",
    r"inhibit",
    r"activat",
    r"suppress",
    r"phosphorylat",
    r"express",
    r"siRNA",
    r"shRNA",
]


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.replace("\n", " ")) if s.strip()]


def hits_for_record(record: dict, aliases: list[str]) -> list[str]:
    text = record.get("abstract", "")
    sentences = split_sentences(text)
    pattern = re.compile("|".join(aliases + KEYWORD_PATTERNS), re.I)
    hits = [s for s in sentences if pattern.search(s)]
    deduped = []
    seen = set()
    for hit in hits:
        if hit not in seen:
            seen.add(hit)
            deduped.append(hit)
    return deduped


def load_rows(root: Path) -> tuple[list[dict], dict[str, dict]]:
    rows = list(csv.DictReader((root / "test_data_biolink.tsv").open(), delimiter="\t"))
    abstracts = json.loads((root / "data" / "pubmed_abstracts.json").read_text())
    return rows, abstracts


def group_rows(rows: list[dict]) -> dict[str, list[dict]]:
    by_pmid: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_pmid[row["PMID"]].append(row)
    return by_pmid


def show_object(root: Path, object_name: str) -> None:
    rows, abstracts = load_rows(root)
    aliases = OBJECT_ALIASES.get(object_name, [re.escape(object_name)])
    for idx, row in enumerate([r for r in rows if r["object"] == object_name], start=1):
        pmid = row["PMID"]
        record = abstracts.get(pmid, {})
        print(
            f"{idx:02d}. PMID {pmid} supported={row['Supported']} "
            f"pred={row['predicate']} subj={row['subject']}"
        )
        print(f"    TITLE: {record.get('title', '')}")
        for hit in hits_for_record(record, aliases)[:5]:
            print(f"    HIT: {hit}")
        if not record.get("abstract"):
            print("    HIT: <missing abstract>")
        print()


def show_pmid(root: Path, pmid: str) -> None:
    rows, abstracts = load_rows(root)
    by_pmid = group_rows(rows)
    record = abstracts.get(pmid, {})
    print(f"PMID {pmid}")
    print(f"TITLE: {record.get('title', '')}")
    print("ROWS:")
    for row in by_pmid.get(pmid, []):
        print(
            f" - {row['subject']} | {row['predicate']} | {row['object']} | supported={row['Supported']}"
        )
    print("ABSTRACT:")
    print(record.get("abstract", "<missing abstract>"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--object")
    group.add_argument("--pmid")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if args.object:
        show_object(root, args.object)
    else:
        show_pmid(root, args.pmid)


if __name__ == "__main__":
    main()
