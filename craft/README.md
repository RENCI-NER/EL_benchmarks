# CRAFT

A linking benchmark from the [CRAFT corpus](https://github.com/UCDenver-ccp/CRAFT) (v5): 97 full-text biomedical articles with expert concept annotation. The CRAFT annotations are licensed CC BY 3.0 (Bada et al., *BMC Bioinformatics* 2012, and the CRAFT project).

## What's included

- **Included:** the core concept annotations for CHEBI, CL, GO (BP, CC, MF), NCBITaxon and UBERON, and MONDO without genotype annotations.
- **Left out, by ontology:**
  - PR: species-agnostic protein classes, a different level from gene/protein identifiers such as NCBIGene;
  - SO and MOP: outside the scope of the linkers evaluated here;
  - the "+extensions" sets, which are CRAFT-specific classes.

**Items.** One item per mention occurrence: the article, its spans, and the paragraph containing it as context. The gold is every concept CRAFT annotated on exactly those spans. Discontinuous mentions ("ES … cells") are written with their pieces joined by spaces. Items are deduplicated to the first occurrence of each distinct (article, mention string), which gives 17,457 items. `truth.jsonl` is a 1,000-item random sample (seed 0):

| | Items |
|---|---|
| UBERON | 278 |
| GO (254 BP, 83 CC, 2 MF) | 339 |
| CHEBI | 148 |
| NCBITaxon | 94 |
| CL | 85 |
| MONDO | 56 |
| discontinuous | 67 |

**Identifiers are CRAFT's own.** MONDO's OBO purls are written as CURIEs, which only changes the syntax. Whether a linker's output matches is decided at evaluation time.

**`closed_world: true`.** CRAFT's annotators chose the concept for each span, so a different concept is wrong, not unjudged. Evaluation should treat it that way, but with a semantic matcher: a different identifier for the same concept is still right.

```bash
uv run python craft/build.py --craft ~/Projects/LitCoin/CRAFT            # --sample N --seed S to change the sample
```

## `truth.jsonl`

```json
{"id": "craft-11319941-16658-16677", "article": "11319941", "text": "<paragraph>", "mention": "cholinergic neurons",
 "spans": [[1219, 1238]], "discontinuous": false, "closed_world": true,
 "judgments": [{"curie": "CL:0000108", "verdict": "correct", "ontology": "CL"}]}
```

`spans` are character offsets into `text`.

`documents.jsonl` has the full text of each article in the sample, one `{"id", "text"}` line per article, with `id` the item's `article`. Use it for document-level steps: abbreviations in particular are often defined in a different paragraph from the mention.

## Known difficulties

These come from a first look at retrieval (NameRes + SapBERT, top 10 each), on 2026-09-29:
- **Recall** of the gold concept was 0.55–0.73 per ontology.
- **Abbreviations are often defined elsewhere in the article** (`ER`, `PM`), but the item's context is a single paragraph. A linker needs a document-level abbreviation map, built from `documents.jsonl`. Few sampled mentions depend on one, though: with abbreviations extracted by gpt-4o-mini, 19 of the 1,000 expand. Others (`EtOH`, `NaF`) are never defined in the article at all.
- **Variants, typos and everyday words** for taxa (`T. rubripes`, `man`, `person`).
