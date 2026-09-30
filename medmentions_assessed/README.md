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

Mentions are left out when the concept MedMentions linked them to has one of these types (`OUT_OF_SCOPE_TYPES` in `build.py`): InformationContentEntity, Publication, Activity, Agent, Device, Phenomenon, GeographicLocation, Cohort, PopulationOfIndividualOrganisms. These mentions are mostly not biomedical entities: "negative", "analysis", "management", "worldwide", "patients". This removes 542 of 2,059 mentions.

A mention's type (`mention_type`) comes from its MedMentions concept. It's null for 57 mentions whose MedMentions concept has no type in the bagel-eval database; those are kept.

Built 2026-09-30: **1,517 mentions** from 101 abstracts, with 2,041 judgments. 1,293 mentions have at least one correct CURIE, and 224 have only incorrect ones. Precision of each system's judged proposals:

| | MedMentions | gpt-oss | o3-mini |
|---|---|---|---|
| judged links | 1,446 | 506 | 259 |
| correct | 0.79 | 0.89 | 0.89 |

## Building

The source is a dump of the bagel-eval Postgres database. Don't commit it: it contains assessor names and role password hashes.

```bash
uv run python medmentions_assessed/build.py prepare --dump ~/Projects/bagel-eval-postgres-dump.sql
uv run python medmentions_assessed/adjudicate/app.py      # http://127.0.0.1:8765
uv run python medmentions_assessed/build.py truth
```

`prepare` writes `work/` (git-ignored). The app appends every decision to `adjudications.jsonl`, which is committed. `truth` writes `truth.jsonl`.

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
 "mention_type": "biolink:Gene", "medmentions_curie": "NCBIGene:51164",
 "judgments": [{"curie": "NCBIGene:51164", "babel_id": "NCBIGene:51164", "label": "DCTN4", "type": "biolink:Gene",
                "verdict": "correct", "basis": "concordant", "proposed_by": ["gpt-oss", "medmentions", "o3-mini-2025-01-31"]}],
 "nodenorm_date": "2026-09-29"}
```

- `curie` is the identifier as assessed.
- `babel_id` is its current NodeNorm-preferred identifier (with conflation) on `nodenorm_date`, or null if NodeNorm doesn't know it.
- `expanded` is the mention after abbreviation expansion, as used when the proposals were made.
- A mention can have several correct CURIEs. Only the judged CURIEs are known to be correct or incorrect; any other CURIE is unjudged.
