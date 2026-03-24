# SEMMEDDB Checker Manual Abstract Review

This repository contains a manual, abstract-level review of the `test_data_biolink.tsv` file from the `Translator-CATRAX/LLM_PMID_Checker` project.

The goal was to inspect each cited PubMed abstract, decide whether the TSV support call is correct for the asserted subject-predicate-object relation, and preserve enough structured evidence to make the review auditable.

## Scope

- Source TSV rows reviewed: `221`
- Unique PMIDs reviewed: `195`
- Review basis: PubMed abstract text only
- Output granularity: one markdown file per PMID
- Row-level judgments: `195` `agree`, `24` `disagree`, `2` `unable_to_assess`

## Repository Contents

- `test_data_biolink.tsv`
  - Downloaded source file under review.
- `data/manual_assessments.json`
  - Canonical manual judgments and explanations.
- `data/pubmed_abstracts.json`
  - Cached PMID titles and abstract text used for the review.
- `data/curie_hydration.json`
  - CURIE lookup results with normalized labels, alias labels, equivalent IDs, and types.
- `data/review_bundle.json`
  - Generated enriched review payload that combines source rows, hydrated IDs, abstracts, snippets, and manual assessments.
- `data/snippet_validation_report.json`
  - Machine validation report for the supporting snippets.
- `reviews/*.md`
  - One human-readable review file per PMID.
- `tools/review_context.py`
  - Helper for inspecting grouped PMID/object review context during review.
- `tools/review_data.py`
  - Shared logic for source-row hydration, snippet extraction, cache seeding, and markdown rendering.
- `tools/write_reviews.py`
  - Rebuilds enriched review data and writes the per-PMID markdown files.
- `tools/validate_reviews.py`
  - Validates the generated supporting snippets against the PMID cache using `linkml-reference-validator`.
- `justfile`
  - Convenience targets for rebuilding and validating the repository artifacts.
- `pyproject.toml`, `uv.lock`
  - `uv`-managed project metadata and lockfile.

## Review Output Format

Each file in `reviews/` contains:

1. PMID and title
2. A plain-language statement of what the abstract actually says
3. The full abstract text
4. Every source triple for that PMID
5. Subject and object IDs from the source TSV
6. Alias/normalization lookup data for those IDs
7. The original dataset support call
8. My manual judgment and rationale
9. Supporting snippet(s) from the abstract for that case

## Identifier Hydration

The source TSV includes `subject_curie` and `object_curie` values. These are hydrated into:

- source labels observed in the TSV
- a normalized lookup label
- alias labels
- a bounded list of equivalent identifiers
- Biolink-style type assignments when available

Hydration is cached in `data/curie_hydration.json`.

The current workflow uses the SRI Node Normalizer service for CURIE lookup and preserves the original TSV labels even when the normalized label differs.

## Supporting Snippets

Each review row includes one or more abstract snippets that support the manual assessment.

These snippets are selected automatically from the abstract using:

- source subject and object labels
- hydrated alias labels
- predicate-direction keywords
- the manual summary and row-level rationale

The displayed snippet text is kept close to the source abstract. For validation, a lightly normalized variant is used when needed so chemistry notation like `pyrazolo[3,4-d]pyrimidinone` can still be checked by the validator.

## Validation

This repository uses `linkml-reference-validator` to validate the supporting snippets against a local PMID cache seeded from `data/pubmed_abstracts.json`.

Current validation status:

- title checks: `193`
- snippet checks: `438`
- invalid checks: `0`

Two PMIDs had no retrievable abstract during the review session, so they have no supporting snippet validation and remain `unable_to_assess`.

## Build And Validate

Install the locked environment:

```bash
uv sync
```

Rebuild hydrated data, reference cache, and markdown reviews:

```bash
just build
```

Validate all supporting snippets:

```bash
just validate
```

The `validate` target depends on `build`, so it always validates the current generated artifacts.

## Notes

- The source TSV originated from:
  - `https://github.com/Translator-CATRAX/LLM_PMID_Checker/blob/main/data/test_data_biolink.tsv`
- This is an abstract-only assessment, not a full-text review.
- Some rows are marked `disagree` because the dataset call is wrong.
- Some rows are marked `disagree` because the grounding or interpretation of the subject/object is wrong even when the paper discusses a related target.
- Some rows are marked `agree` on unsupported calls because the abstract is clearly about a different entity, mechanism, or meaning of the term.
