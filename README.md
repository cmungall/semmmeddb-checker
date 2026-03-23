# SEMMEDDB Checker Manual Abstract Review

This repository contains a manual, abstract-level review of the `test_data_biolink.tsv` file from the `Translator-CATRAX/LLM_PMID_Checker` project.

The goal was to inspect each cited PubMed abstract and decide whether the TSV's support call is correct for the asserted subject-predicate-object relation.

## Scope

- Source TSV rows reviewed: `221`
- Unique PMIDs reviewed: `195`
- Review basis: PubMed abstract text only
- Output granularity: one markdown file per PMID

## What Is In The Repository

- `test_data_biolink.tsv`
  - Downloaded source file that was manually reviewed.
- `data/pubmed_abstracts.json`
  - Cached abstract/title text used during review.
- `data/manual_assessments.json`
  - Canonical structured review output.
- `data/review_groups.json`
  - Grouped review context used during the workflow.
- `reviews/*.md`
  - One human-readable review file per PMID.
- `tools/review_context.py`
  - Helper for inspecting grouped PMID/object review context.
- `tools/write_reviews.py`
  - Generates the per-PMID markdown files from `data/manual_assessments.json`.

## Review Method

For each PMID, I read the abstract and wrote a short summary of what the abstract actually says about the relevant predicate direction, then evaluated every row attached to that PMID.

Each row in `data/manual_assessments.json` is labeled as one of:

- `agree`
  - The TSV support call matches what the abstract says.
- `disagree`
  - The TSV support call does not match the abstract.
- `unable_to_assess`
  - No abstract was retrievable in the review session, so no direct abstract-based judgment was possible.

Important constraint:

- This is an abstract-only assessment, not a full-text review.
- Some rows are marked `disagree` because the subject grounding is wrong even when the paper does discuss the target.
- Some rows are marked `agree` on unsupported calls because the abstract is about a different target, pathway, or sense of the term entirely.

## Result Summary

Row-level assessment counts:

- `agree`: `195`
- `disagree`: `24`
- `unable_to_assess`: `2`

Two PMIDs had no retrievable abstract during the session and were therefore marked `unable_to_assess`.

## Per-PMID Review Format

Each file in `reviews/` contains:

1. PMID and title
2. A plain-language statement of what the abstract does say
3. Every TSV assertion for that PMID
4. The original dataset support call
5. My manual judgment and rationale

## Regenerating The Markdown Reviews

From the repository root:

```bash
python3 tools/write_reviews.py
```

To inspect review context for a specific PMID:

```bash
python3 tools/review_context.py --pmid 12511421
```

To inspect all rows for a specific object:

```bash
python3 tools/review_context.py --object "Il2-inducible t-cell kinase"
```

## Notes

- The source TSV originated from:
  - `https://github.com/Translator-CATRAX/LLM_PMID_Checker/blob/main/data/test_data_biolink.tsv`
- Repository contents include both the structured review data and the generated markdown outputs so the results can be inspected without rerunning the workflow.
