# EL_benchmarks

Benchmarks for evaluating biomedical entity linking: a mention in text → a Babel/NodeNorm identifier. Named-entity recognition is out of scope; mentions come with the benchmark.

Datasets are meant to be static: each one is built by a documented script from a named source, and the built files are committed.

Benchmarks hold the source's own identifiers. Deciding whether a linker's output matches one (the same identifier, or the same concept in some Babel release) is up to the evaluation, so a benchmark doesn't change meaning with a Babel release. Each benchmark has a `truth.jsonl` of items and a `documents.jsonl` with the full text of each source document, for steps that work on whole documents, such as abbreviation extraction. Each item says whether it is `closed_world`: whether an identifier that doesn't match the gold is wrong (CRAFT) or only unjudged (MedMentions-assessed).

| Directory | What it is | Status |
|---|---|---|
| [`medmentions_assessed/`](medmentions_assessed/) | MedMentions mentions whose proposed links (from MedMentions, gpt-oss, o3-mini) were judged by two people in bagel-eval, plus adjudication of their disagreements | built: 1,489 mentions, 2,006 judgments |
| [`abbreviations/`](abbreviations/) | Parentheticals in 100 held-out MedMentions abstracts, labeled by whether they define an abbreviation for the same thing as the phrase (same / instance / other); for a linker's abbreviation step | items built: 424; labeling in progress |
| [`craft/`](craft/) | CRAFT core concept annotations (CHEBI, CL, GO, NCBITaxon, UBERON, MONDO), one item per distinct article mention, sampled | built: 1,000 items |

```bash
uv sync
uv run pytest
```
