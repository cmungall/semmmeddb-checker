#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from linkml_reference_validator.etl.reference_fetcher import ReferenceFetcher
from linkml_reference_validator.models import ReferenceContent, ReferenceValidationConfig


NODE_NORMALIZER_URL = "https://nodenormalization-sri.renci.org/1.5/get_normalized_nodes"
HYDRATION_BATCH_SIZE = 50
MAX_ALIAS_LABELS = 12
MAX_EQUIVALENT_IDENTIFIERS = 20
MAX_SNIPPETS_PER_ROW = 2
COMMON_STOPWORDS = {
    "a",
    "about",
    "all",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "but",
    "by",
    "can",
    "concerns",
    "describes",
    "does",
    "downstream",
    "during",
    "for",
    "from",
    "gives",
    "has",
    "have",
    "here",
    "in",
    "including",
    "induces",
    "inhibits",
    "into",
    "is",
    "it",
    "its",
    "mechanism",
    "mentioned",
    "not",
    "of",
    "on",
    "or",
    "paper",
    "pathway",
    "protein",
    "reported",
    "shows",
    "signaling",
    "study",
    "supports",
    "target",
    "that",
    "the",
    "their",
    "this",
    "through",
    "to",
    "was",
    "were",
    "what",
    "while",
    "with",
}
GENERIC_ALIAS_LABELS = {
    "chemical",
    "compound",
    "protein",
    "gene",
    "factor",
    "agent",
    "acid",
    "rna",
}
PREDICATE_KEYWORDS = {
    "biolink:increases_amount_or_activity_of": [
        "increase",
        "increases",
        "increased",
        "up-regulates",
        "up-regulate",
        "upregulated",
        "up-regulation",
        "activates",
        "activation",
        "induces",
        "induced",
        "expression",
    ],
    "biolink:decreases_amount_or_activity_of": [
        "decrease",
        "decreases",
        "decreased",
        "down-regulates",
        "down-regulate",
        "downregulated",
        "down-regulation",
        "inhibits",
        "inhibited",
        "inhibitor",
        "suppresses",
        "suppressed",
        "antagonist",
        "inactivates",
        "inactivated",
    ],
}
OBJECT_ALIAS_HINTS = {
    "Tumor necrosis factor receptor superfamily, member 10a": [
        "DR4",
        "TRAIL-R1",
        "death receptor 4",
        "TRAIL receptor 1",
    ],
    "Il2-inducible t-cell kinase": [
        "ITK",
        "interleukin-2-inducible T-cell kinase",
        "IL-2-inducible T-cell kinase",
    ],
    "dual specificity tyrosine phosphorylation regulated kinase 1A": [
        "DYRK1A",
        "dual-specificity tyrosine-phosphorylation-regulated kinase 1A",
    ],
    "diacylglycerol kinase beta": [
        "DGK beta",
        "DGK-B",
        "DGKB",
    ],
    "glucokinase": [
        "GCK",
        "glucokinase",
    ],
    "hexokinase 1": [
        "HK1",
        "hexokinase 1",
        "hexokinase",
    ],
    "cyclin dependent kinase like 2": [
        "CDKL2",
        "cyclin-dependent kinase-like 2",
    ],
    "Deoxycytidine kinase": [
        "dCK",
        "deoxycytidine kinase",
    ],
    "death associated protein kinase 3": [
        "DAPK3",
        "ZIPK",
        "death-associated protein kinase 3",
    ],
    "death associated protein kinase 1": [
        "DAPK1",
        "DAP kinase",
        "death-associated protein kinase 1",
    ],
    "Death-associated protein kinase 1": [
        "DAPK1",
        "DAP kinase",
        "death-associated protein kinase 1",
    ],
    "CDC like kinase 1": [
        "CLK1",
        "Cdc-like kinase 1",
        "CDC-like kinase 1",
    ],
    "Cdc-like kinase 1": [
        "CLK1",
        "Cdc-like kinase 1",
        "CDC-like kinase 1",
    ],
    "transient receptor potential cation channel subfamily M member 6": [
        "TRPM6",
        "transient receptor potential melastatin 6",
    ],
    "aurora kinase B": [
        "AurB",
        "AURKB",
        "aurora kinase B",
    ],
    "Aurora kinase b": [
        "AurB",
        "AURKB",
        "aurora kinase B",
    ],
    "serine/threonine kinase 3": [
        "MST2",
        "serine/threonine kinase 3",
    ],
    "toll like receptor 1": [
        "TLR1",
        "toll-like receptor 1",
    ],
    "cyclin dependent kinase inhibitor 3": [
        "CDKN3",
        "cyclin-dependent kinase inhibitor 3",
    ],
    "checkpoint kinase 2": [
        "CHEK2",
        "CHK2",
        "checkpoint kinase 2",
    ],
    "Cyclin-dependent kinase-like 3": [
        "CDKL3",
        "cyclin-dependent kinase-like 3",
    ],
}


@dataclass
class ReviewBundle:
    bundle: dict[str, Any]
    curie_hydration: dict[str, Any]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def split_sentences(text: str) -> list[str]:
    cleaned = text.replace("\n", " ").strip()
    if not cleaned:
        return []
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if s.strip()]


def strip_class_suffix(text: str) -> str:
    return re.sub(r"\s*\[[^\]]+\]\s*$", "", text).strip()


def collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_text(text: str) -> str:
    return collapse_whitespace(text).casefold()


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9+/\-.]*", text)


def significant_terms(*texts: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for text in texts:
        for token in tokenize(text):
            normalized = token.casefold().strip(".,;:()[]{}")
            if not normalized:
                continue
            if normalized in COMMON_STOPWORDS:
                continue
            if len(normalized) < 3 and not token.isupper():
                continue
            if normalized not in seen:
                seen.add(normalized)
                terms.append(normalized)
    return terms


def unique_preserving_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def get_ncbi_email() -> str:
    env_email = os.environ.get("NCBI_EMAIL")
    if env_email:
        return env_email
    try:
        result = subprocess.run(
            ["git", "config", "--get", "user.email"],
            check=True,
            capture_output=True,
            text=True,
        )
        email = result.stdout.strip()
        if email:
            return email
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return "linkml-reference-validator@example.com"


def validator_config(root: Path) -> ReferenceValidationConfig:
    return ReferenceValidationConfig(
        cache_dir=root / "references_cache",
        email=get_ncbi_email(),
        rate_limit_delay=0.0,
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_source_rows(root: Path) -> list[dict[str, str]]:
    with (root / "test_data_biolink.tsv").open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def labels_by_curie(rows: list[dict[str, str]]) -> dict[str, list[str]]:
    by_curie: dict[str, list[str]] = {}
    for row in rows:
        for key, label_key in (("subject_curie", "subject"), ("object_curie", "object")):
            curie = row[key]
            label = row[label_key]
            by_curie.setdefault(curie, [])
            by_curie[curie].append(label)
            stripped = strip_class_suffix(label)
            if stripped != label:
                by_curie[curie].append(stripped)
    return {curie: unique_preserving_order(labels) for curie, labels in by_curie.items()}


def normalize_node_payload(curie: str, source_labels: list[str], node: dict[str, Any] | None) -> dict[str, Any]:
    preferred_id = curie
    preferred_label = source_labels[0] if source_labels else curie
    equivalent_identifiers: list[dict[str, str]] = []
    alias_labels = list(source_labels)
    types: list[str] = []
    resolved = False

    if node:
        resolved = True
        node_id = node.get("id") or {}
        preferred_id = node_id.get("identifier", preferred_id)
        preferred_label = node_id.get("label") or preferred_label
        types = [value for value in node.get("type", []) if isinstance(value, str)]
        for eq in node.get("equivalent_identifiers", []) or []:
            identifier = eq.get("identifier")
            label = eq.get("label")
            if not identifier:
                continue
            entry: dict[str, str] = {"identifier": identifier}
            if label:
                entry["label"] = label
                alias_labels.append(label)
            equivalent_identifiers.append(entry)

    alias_labels = [
        label
        for label in unique_preserving_order([preferred_label] + alias_labels)
        if label and label.casefold() not in GENERIC_ALIAS_LABELS
    ]

    return {
        "requested_curie": curie,
        "resolved": resolved,
        "preferred_curie": preferred_id,
        "preferred_label": preferred_label,
        "source_labels": source_labels,
        "alias_labels": alias_labels[:MAX_ALIAS_LABELS],
        "equivalent_identifiers": equivalent_identifiers[:MAX_EQUIVALENT_IDENTIFIERS],
        "types": types,
    }


def fetch_node_normalizer_batch(curies: list[str]) -> dict[str, Any]:
    body = json.dumps({"curies": curies}).encode("utf-8")
    request = urllib.request.Request(
        NODE_NORMALIZER_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def ensure_curie_hydration(root: Path, rows: list[dict[str, str]], refresh: bool = False) -> dict[str, Any]:
    path = root / "data" / "curie_hydration.json"
    existing = {} if refresh or not path.exists() else read_json(path)
    source_labels = labels_by_curie(rows)
    curies = sorted(source_labels)

    unresolved = [curie for curie in curies if refresh or curie not in existing]
    if unresolved:
        fetched: dict[str, Any] = {}
        for start in range(0, len(unresolved), HYDRATION_BATCH_SIZE):
            batch = unresolved[start:start + HYDRATION_BATCH_SIZE]
            try:
                fetched.update(fetch_node_normalizer_batch(batch))
            except urllib.error.URLError:
                for curie in batch:
                    fetched[curie] = None
            time.sleep(0.1)
        for curie in unresolved:
            existing[curie] = normalize_node_payload(curie, source_labels[curie], fetched.get(curie))

    for curie in curies:
        if curie not in existing:
            existing[curie] = normalize_node_payload(curie, source_labels[curie], None)
        else:
            existing[curie]["source_labels"] = source_labels[curie]
            merged_aliases = unique_preserving_order(source_labels[curie] + existing[curie].get("alias_labels", []))
            existing[curie]["alias_labels"] = merged_aliases[:MAX_ALIAS_LABELS]

    ordered = {curie: existing[curie] for curie in curies}
    write_json(path, ordered)
    return ordered


def seed_reference_cache(root: Path, abstracts: dict[str, Any]) -> None:
    fetcher = ReferenceFetcher(validator_config(root))
    cache_dir = validator_config(root).cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    for pmid, record in abstracts.items():
        content = collapse_whitespace(record.get("abstract", ""))
        content_type = "abstract_only" if content else "unavailable"
        fetcher._save_to_disk(
            ReferenceContent(
                reference_id=f"PMID:{pmid}",
                title=record.get("title", ""),
                content=content or None,
                content_type=content_type,
            )
        )


def phrase_variants(label: str, hydration: dict[str, Any]) -> list[tuple[str, int]]:
    phrases: list[tuple[str, int]] = []
    base_labels = [label, strip_class_suffix(label), hydration.get("preferred_label", "")]
    alias_labels = hydration.get("alias_labels", [])
    hint_labels = OBJECT_ALIAS_HINTS.get(label, [])
    for text in unique_preserving_order([value for value in base_labels + alias_labels + hint_labels if value]):
        stripped = strip_class_suffix(text)
        if len(stripped) < 3:
            continue
        weight = 8 if text in base_labels else 4
        if text in hint_labels:
            weight = 6
        phrases.append((normalize_text(stripped), weight))
    return phrases


def sentence_score(
    sentence: str,
    phrases: list[tuple[str, int]],
    tokens: list[str],
    predicate: str,
) -> int:
    lowered = normalize_text(sentence)
    token_set = {term.casefold() for term in tokenize(sentence)}
    score = 0
    for phrase, weight in phrases:
        if phrase and phrase in lowered:
            score += weight
    for token in tokens:
        if token in token_set:
            score += 1
    for keyword in PREDICATE_KEYWORDS.get(predicate, []):
        if keyword.casefold() in lowered:
            score += 2
    return score


def select_supporting_snippets(
    abstract: str,
    source_row: dict[str, str],
    summary: str,
    reason: str,
    subject_hydration: dict[str, Any],
    object_hydration: dict[str, Any],
) -> list[str]:
    sentences = split_sentences(abstract)
    if not sentences:
        return []
    phrases = phrase_variants(source_row["subject"], subject_hydration) + phrase_variants(
        source_row["object"], object_hydration
    )
    tokens = significant_terms(
        source_row["subject"],
        strip_class_suffix(source_row["subject"]),
        source_row["object"],
        summary,
        reason,
        subject_hydration.get("preferred_label", ""),
        object_hydration.get("preferred_label", ""),
        " ".join(subject_hydration.get("alias_labels", [])),
        " ".join(object_hydration.get("alias_labels", [])),
    )

    scored: list[tuple[int, int, str]] = []
    for idx, sentence in enumerate(sentences):
        scored.append((sentence_score(sentence, phrases, tokens, source_row["predicate"]), idx, sentence))
    scored.sort(key=lambda item: (-item[0], item[1]))

    chosen = [item for item in scored if item[0] > 0][:MAX_SNIPPETS_PER_ROW]
    if not chosen:
        chosen = scored[:1]

    ordered = [sentence for _, _, sentence in sorted(chosen, key=lambda item: item[1])]
    return unique_preserving_order(ordered)


def match_source_row(source_rows: list[dict[str, str]], assessment_row: dict[str, str]) -> dict[str, str]:
    matches = [
        row for row in source_rows
        if row["subject"] == assessment_row["subject"]
        and row["predicate"] == assessment_row["predicate"]
        and row["object"] == assessment_row["object"]
    ]
    if not matches:
        raise ValueError(f"No source row found for {assessment_row}")
    return matches[0]


def build_review_bundle(root: Path, refresh_hydration: bool = False) -> ReviewBundle:
    rows = load_source_rows(root)
    assessments = read_json(root / "data" / "manual_assessments.json")
    abstracts = read_json(root / "data" / "pubmed_abstracts.json")
    hydration = ensure_curie_hydration(root, rows, refresh=refresh_hydration)
    seed_reference_cache(root, abstracts)

    by_pmid: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_pmid.setdefault(row["PMID"], []).append(row)

    bundle: dict[str, Any] = {}
    for pmid, payload in sorted(assessments.items(), key=lambda item: int(item[0])):
        abstract_record = abstracts.get(pmid, {})
        abstract_text = collapse_whitespace(abstract_record.get("abstract", ""))
        enriched_rows = []
        source_rows = by_pmid.get(pmid, [])
        for row in payload["rows"]:
            source_row = match_source_row(source_rows, row)
            subject_hydration = hydration.get(source_row["subject_curie"], {
                "requested_curie": source_row["subject_curie"],
                "preferred_curie": source_row["subject_curie"],
                "preferred_label": source_row["subject"],
                "source_labels": [source_row["subject"]],
                "alias_labels": [source_row["subject"]],
                "equivalent_identifiers": [],
                "types": [],
                "resolved": False,
            })
            object_hydration = hydration.get(source_row["object_curie"], {
                "requested_curie": source_row["object_curie"],
                "preferred_curie": source_row["object_curie"],
                "preferred_label": source_row["object"],
                "source_labels": [source_row["object"]],
                "alias_labels": [source_row["object"]],
                "equivalent_identifiers": [],
                "types": [],
                "resolved": False,
            })
            enriched_rows.append({
                "source_row": source_row,
                "assessment": row["assessment"],
                "reason": row["reason"],
                "subject_hydration": subject_hydration,
                "object_hydration": object_hydration,
                "supporting_snippets": select_supporting_snippets(
                    abstract_text,
                    source_row,
                    payload["summary"],
                    row["reason"],
                    subject_hydration,
                    object_hydration,
                ),
            })

        bundle[pmid] = {
            "pmid": pmid,
            "title": payload.get("title", ""),
            "abstract": abstract_text,
            "summary": payload["summary"],
            "rows": enriched_rows,
        }

    review_bundle = {
        "generated_at_utc": now_utc(),
        "pmids": bundle,
    }
    write_json(root / "data" / "review_bundle.json", review_bundle)
    return ReviewBundle(bundle=bundle, curie_hydration=hydration)


def hydration_summary_lines(prefix: str, hydration: dict[str, Any]) -> list[str]:
    lines = [
        f"- {prefix} ID: `{hydration['requested_curie']}`",
        f"- {prefix} lookup label: `{hydration['preferred_label']}`",
    ]
    if hydration["preferred_curie"] != hydration["requested_curie"]:
        lines.append(f"- {prefix} normalized ID: `{hydration['preferred_curie']}`")
    aliases = hydration.get("alias_labels", [])
    if aliases:
        rendered = ", ".join(f"`{alias}`" for alias in aliases[:MAX_ALIAS_LABELS])
        lines.append(f"- {prefix} alias labels: {rendered}")
    types = hydration.get("types", [])
    if types:
        lines.append(f"- {prefix} lookup types: {', '.join(f'`{value}`' for value in types[:6])}")
    return lines


def render_review(pmid: str, payload: dict[str, Any]) -> str:
    lines = [
        f"# PMID {pmid}",
        "",
        f"Title: {payload['title']}",
        "",
        "What the abstract does say:",
        payload["summary"],
        "",
        "Abstract:",
        payload["abstract"] or "<missing abstract>",
        "",
        "Assertions:",
    ]

    for idx, row in enumerate(payload["rows"], start=1):
        source = row["source_row"]
        lines.extend(
            [
                "",
                f"## Assertion {idx}",
                "",
                "Source triple:",
                f"- Subject label: `{source['subject']}`",
                *hydration_summary_lines("Subject", row["subject_hydration"]),
                f"- Predicate: `{source['predicate']}`",
                f"- Object label: `{source['object']}`",
                *hydration_summary_lines("Object", row["object_hydration"]),
                f"- PMID: `{source['PMID']}`",
                f"- Dataset call: `{source['Supported']}`",
                "",
                "Assessment:",
                f"- My assessment: `{row['assessment']}`",
                f"- Why: {row['reason']}",
                "",
                "Supporting snippets:",
            ]
        )
        snippets = row.get("supporting_snippets", [])
        if snippets:
            for snippet in snippets:
                lines.append(f"> {snippet}")
        else:
            lines.append("- <no snippet available>")

    lines.append("")
    return "\n".join(lines)
