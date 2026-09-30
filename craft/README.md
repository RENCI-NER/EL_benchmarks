# CRAFT (planned)

The [CRAFT corpus](https://github.com/UCDenver-ccp/CRAFT) concept annotations, adapted to Babel identifiers: 97 full-text articles with expert annotation of anatomy, cells, GO, chemicals, taxa, proteins and diseases.

These are the findings from a first look (2026-09-29) at the converted file `craft_corpus_normalized.jsonl` (6,649 paragraphs, 96,074 mentions) and a 360-mention retrieval sample. They're the adaptations the conversion needs:

- **Drop SO and MOP.** Sequence Ontology (12.2k mentions) and MOP (341) aren't in Babel, so no Babel-based linker can link them. That's about 13% of mentions.
- **Proteins need a rule.** PR annotations (24% of mentions) are mostly species-agnostic protein classes, while Babel conflates genes and proteins into species-specific genes. Retrieval recall reads as 12% for PR because the top candidate is usually the right gene at a different level (e.g. `BMPR1A` → `NCBIGene:657`). We need a rule such as "the gene of the article's organism counts as correct for a PR class".
- **Add MONDO.** The corpus has MONDO annotations (`concept-annotation/MONDO`), but the existing conversion leaves them out.
- **Discontinuous spans.** About 2% of mentions (`vestibular ... sensory neurons`) need their pieces joined.
- **Abbreviations are defined across paragraphs.** Full text needs a document-level abbreviation map (`ER`, `PM`, `EtOH`, `NaF`).
- **Sample distinct pairs.** Use distinct (article, mention string) pairs, with the paragraph as context. The 96k mentions contain only 10k distinct strings.

In the sample, retrieval recall (NameRes + SapBERT + NodeNorm, top 10 each) was 0.55–0.73 for UBERON, GO, CHEBI, CL and NCBITaxon.
