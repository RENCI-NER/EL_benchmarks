# MedMentions, assessed

Human judgments of proposed links for MedMentions mentions. They were collected in bagel-eval, where assessors were asked whether a proposed CURIE is the **exact** match for the mention in its abstract. The proposals came from the MedMentions annotations and from BAGEL runs with gpt-oss and o3-mini, which had labeled them exact matches.

## Which judgments are in the truth set

Each judgment is for one (mention, CURIE) pair. Most pairs were judged by two assessors, working in fixed pairs.

| Case | Verdict | `basis` |
|---|---|---|
| both assessors agreed | correct | `concordant` |
| both disagreed | incorrect | `concordant` |
| one agreed, one disagreed | the adjudicator's decision | `adjudicated` |
| judged by one assessor only | excluded | |
| any assessor answered "unsure" | excluded | |

The verdicts are meant strictly: correct means the CURIE is the exact match, not a broader or related concept. Assessors weren't all equally strict, which is why only agreement between two assessors, or an adjudication, counts. The adjudicator is Chris. Conflicts within his own assessment pair were resolved in his favor without review; the rest are decided with the adjudication app.

"Hong" and "Hong Yi" are the same assessor. No assessor names appear in any output.

## Scope

Scope is decided once by `build.py scope` and frozen in the committed `scope.jsonl`, so rebuilding the truth set never depends on a Babel release. A mention's type (`mention_type`) is the type of the concept MedMentions linked it to: bagel-eval's type if it has one, otherwise NodeNorm's at the time `scope` ran. `type_source` records which (the 2026-09-30 run used Babel 2026jul22 for 50 untyped concepts). Mentions are left out when:
- that type is in `OUT_OF_SCOPE_TYPES` (`build.py`): InformationContentEntity, Publication, Activity, Agent, Device, Phenomenon, GeographicLocation, Cohort, PopulationOfIndividualOrganisms. These are mostly not biomedical entities ("negative", "analysis", "worldwide", "patients", fields of study like "dermatology");
- or the concept is in `OUT_OF_SCOPE_CONCEPTS`: 9 MedMentions concepts that have no type anywhere and aren't entities ("incorporate", "calculated", "nucleated", "severe disorder", ...).

Together these remove 570 of 2,059 mentions. 27 mentions stay with no type. Their MedMentions concepts are UMLS CUIs that are retired or missing from Babel, but they're real entities (colorectal cancer, TACE, ground glass opacity, gene polymorphism, immune response).

Built 2026-09-30: **1,489 mentions** from 101 abstracts, with 2,006 judgments. 1,273 mentions have at least one correct CURIE, and 216 have only incorrect ones. Precision of each system's judged proposals:

| | MedMentions | gpt-oss | o3-mini |
|---|---|---|---|
| judged links | 1,419 | 498 | 259 |
| correct | 0.79 | 0.88 | 0.89 |

## Building

The source is a dump of the bagel-eval Postgres database. Don't commit it: it contains assessor names and role password hashes.

```bash
uv run python medmentions_assessed/build.py prepare --dump ~/Projects/bagel-eval-postgres-dump.sql
uv run python medmentions_assessed/adjudicate/app.py      # http://127.0.0.1:8765
uv run python medmentions_assessed/build.py scope      # only to change the scope deliberately
uv run python medmentions_assessed/build.py truth
```

`prepare` writes `work/` (git-ignored). The app appends every decision to `adjudications.jsonl`, which is committed. `truth` writes `truth.jsonl` from `work/`, `adjudications.jsonl` and `scope.jsonl`, without calling any service.

## Adjudication app

The app shows one mention per screen: the abstract with the mention highlighted, the mention string, and each disputed term (label, CURIE, type, definition). It doesn't show who voted which way.

| Terms on screen | Keys |
|---|---|
| one | `y` correct, `n` wrong |
| several | `1`–`3` only that one is correct, `b` all, `n` none, `Shift`+number to toggle a term then `Enter` to submit |

`u` skips a mention (it's offered again at the end), and `z` undoes the last decision. Keys pressed while a decision is saving are ignored. Every decision is written immediately, so you can stop and restart at any time.

## `truth.jsonl`

One line per mention:

```json
{"id": "mm-assessed-0", "pmid": "25763772", "text": "<title + abstract>", "mention": "DCTN4", "expanded": "dynactin 4",
 "mention_type": "biolink:Gene", "medmentions_curie": "NCBIGene:51164", "closed_world": false,
 "judgments": [{"curie": "NCBIGene:51164", "label": "DCTN4", "type": "biolink:Gene", "verdict": "correct",
                "basis": "concordant", "proposed_by": ["gpt-oss", "medmentions", "o3-mini-2025-01-31"]}]}
```

- **`curie`** is the identifier exactly as assessed. There's no normalization: whether a linker's output matches a judged CURIE (same identifier, or the same Babel concept under some release and conflation setting) is decided at evaluation time.
- **`label`** and **`type`** are what bagel-eval showed the assessors, or null if it had none.
- **`expanded`** is the mention after abbreviation expansion, as used when the proposals were made.
- **`closed_world: false`** means only the judged CURIEs are known to be correct or incorrect. Any other CURIE is unjudged, not wrong. A mention can have several correct CURIEs.
