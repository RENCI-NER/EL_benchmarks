"""
Builds the MedMentions-assessed linking benchmark from a dump of the bagel-eval database.

    python medmentions_assessed/build.py prepare --dump ~/Projects/bagel-eval-postgres-dump.sql
    python medmentions_assessed/adjudicate/app.py          # adjudicate the conflicts
    python medmentions_assessed/build.py truth              # write medmentions_assessed/truth.jsonl

Each assessment says whether a proposed CURIE is the exact match for a mention (the proposals were exact matches
from MedMentions, gpt-oss or o3-mini). A (mention, CURIE) judgment enters the truth set when:
- two assessors gave the same verdict (both agree -> correct, both disagree -> incorrect), or
- they conflicted and the adjudicator decided. Conflicts within the adjudicator's own assessment pair are
  resolved in the adjudicator's favor without review.
Single-assessor judgments and judgments involving "unsure" are left out, and so are mentions whose MedMentions
concept has a type in OUT_OF_SCOPE_TYPES (type from bagel-eval, else current NodeNorm) or is in OUT_OF_SCOPE_CONCEPTS.

Outputs contain no assessor names.
"""
import argparse
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

import httpx

HERE = Path(__file__).parent
WORK = HERE / "work"
CONFLICTS = WORK / "conflicts.jsonl"
JUDGMENTS = WORK / "judgments.jsonl"
ADJUDICATIONS = HERE / "adjudications.jsonl"
TRUTH = HERE / "truth.jsonl"

TABLES = ("abstracts", "recognized_entities", "assessment", "results", "entities")
ASSESSOR_ALIASES = {"Hong Yi": "Hong", "Sua\\parna": "Suparna"}  # same people under two names
ADJUDICATOR = "Chris"
# Mentions whose MedMentions-assigned concept has one of these types are not biomedical entities worth linking
# ("negative", "analysis", "management", "worldwide", "patients", ...) and are left out of the truth set.
OUT_OF_SCOPE_TYPES = {
    "biolink:InformationContentEntity", "biolink:Publication", "biolink:Activity", "biolink:Agent", "biolink:Device",
    "biolink:Phenomenon", "biolink:GeographicLocation", "biolink:Cohort", "biolink:PopulationOfIndividualOrganisms",
}
# MedMentions concepts (UMLS 2017) with no type in bagel-eval or current NodeNorm that aren't entities either;
# mentions linked to them are left out. Untyped concepts that are real entities (e.g. retired CUIs for colorectal
# cancer or TACE) are kept.
OUT_OF_SCOPE_CONCEPTS = {
    "UMLS:C0243126",  # incorporate / incorporation
    "UMLS:C1443182",  # calculated
    "UMLS:C1979936",  # nucleated
    "UMLS:C0220911",  # serological
    "UMLS:C0024752",  # human (retired)
    "UMLS:C1836348",  # severe disorder
    "UMLS:C1858576",  # heterogeneous disorders
    "UMLS:C2986808",  # iTRAQ-labeled -> "Radioactive Label"
    "UMLS:C1320357",  # pain intensity -> "Pain Distress Question"
}
NODENORM = "https://nodenormalization-sri.renci.org/get_normalized_nodes"


def _unescape(field: str):
    if field == r"\N":
        return None
    escapes = {"t": "\t", "n": "\n", "r": "\r", "\\": "\\"}
    out, i = [], 0
    while i < len(field):
        if field[i] == "\\" and i + 1 < len(field) and field[i + 1] in escapes:
            out.append(escapes[field[i + 1]])
            i += 2
        else:
            out.append(field[i])
            i += 1
    return "".join(out)


def read_copy_tables(path, tables=TABLES) -> dict[str, list[dict]]:
    """Reads the COPY ... FROM stdin blocks of the given tables from a plain-text pg_dump / pg_dumpall."""
    rows = {t: [] for t in tables}
    current = columns = None
    with open(path, encoding="utf-8") as stream:
        for line in stream:
            if current is None:
                if line.startswith("COPY public."):
                    name = line[len("COPY public."):].split(" ", 1)[0]
                    if name in rows:
                        current = name
                        columns = [c.strip() for c in line[line.index("(") + 1:line.index(")")].split(",")]
                continue
            if line.rstrip("\n") == r"\.":
                current = None
                continue
            rows[current].append(dict(zip(columns, (_unescape(f) for f in line.rstrip("\n").split("\t")))))
    return rows


def judgment_status(verdicts: dict[str, str]) -> str:
    """concordant_correct | concordant_incorrect | conflict | single | unsure"""
    values = list(verdicts.values())
    if "unsure" in values:
        return "unsure"
    if len(values) == 1:
        return "single"
    if set(values) == {"agree"}:
        return "concordant_correct"
    if set(values) == {"disagree"}:
        return "concordant_incorrect"
    return "conflict"


def normalize(curies: list[str]) -> dict[str, dict]:
    """Current NodeNorm preferred identifier, label, type and description for each CURIE (None if unknown)."""
    out = {}
    with httpx.Client(timeout=120) as client:
        for start in range(0, len(curies), 500):
            batch = curies[start:start + 500]
            response = client.post(NODENORM, json={"curies": batch, "conflate": True, "drug_chemical_conflate": True,
                                                   "description": True})
            response.raise_for_status()
            for curie, node in response.json().items():
                out[curie] = None if not node else {
                    "babel_id": node["id"]["identifier"], "label": node["id"].get("label", ""),
                    "type": node["type"][0], "description": node["id"].get("description", "")}
    return out


def prepare(dump: Path) -> None:
    t = read_copy_tables(dump)
    abstracts = {r["pmid"]: r["abstract"] for r in t["abstracts"]}
    mentions = {r["id"]: r for r in t["recognized_entities"]}
    entities = {r["identifier"]: r for r in t["entities"]}
    proposed = defaultdict(set)
    medmentions = {}
    for r in t["results"]:
        if r["identifier"]:
            proposed[(r["idx"], r["identifier"])].add(r["model"])
            if r["model"] == "medmentions":
                medmentions[r["idx"]] = r["identifier"]
    verdicts = defaultdict(dict)
    for r in t["assessment"]:
        verdicts[(r["idx"], r["identifier"])][ASSESSOR_ALIASES.get(r["assessor"], r["assessor"])] = r["assessment"]
    judged_mentions = {idx for idx, _ in verdicts}
    normalized = normalize(sorted({curie for _, curie in verdicts}
                                  | {medmentions[idx] for idx in judged_mentions if idx in medmentions}))

    def mention_type(idx):
        """Type of the concept MedMentions linked the mention to: bagel-eval's, else current NodeNorm's."""
        curie = medmentions.get(idx)
        return entities.get(curie, {}).get("type") or (normalized.get(curie) or {}).get("type") or None

    WORK.mkdir(exist_ok=True)
    judgments, queue = [], defaultdict(list)
    for (idx, curie), by_assessor in sorted(verdicts.items(), key=lambda kv: (int(kv[0][0]), kv[0][1])):
        status = judgment_status(by_assessor)
        stored = entities.get(curie, {})
        node = normalized.get(curie) or {}
        judgment = {
            "mention_id": idx, "curie": curie, "babel_id": node.get("babel_id"),
            "label": stored.get("label") or node.get("label", ""),
            "type": stored.get("type") or node.get("type", ""),
            "description": stored.get("description") or node.get("description", ""),
            "proposed_by": sorted(proposed.get((idx, curie), [])),
            "status": status,
        }
        if status == "conflict" and ADJUDICATOR in by_assessor:
            judgment["status"] = "adjudicated_correct" if by_assessor[ADJUDICATOR] == "agree" \
                else "adjudicated_incorrect"
        judgments.append(judgment)
        if judgment["status"] == "conflict":
            queue[idx].append(judgment)
    with open(JUDGMENTS, "w") as out:
        for j in judgments:
            out.write(json.dumps(j) + "\n")
    with open(CONFLICTS, "w") as out:
        for idx in sorted(queue, key=int):
            m = mentions[idx]
            out.write(json.dumps({"mention_id": idx, "pmid": m["pmid"], "abstract": abstracts[m["pmid"]],
                                  "mention": m["original_text"], "expanded": m["expanded_text"],
                                  "terms": queue[idx]}) + "\n")
    with open(WORK / "mentions.json", "w") as out:
        json.dump({idx: {"pmid": mentions[idx]["pmid"], "mention": mentions[idx]["original_text"],
                         "expanded": mentions[idx]["expanded_text"], "medmentions_curie": medmentions.get(idx),
                         "mention_type": mention_type(idx)}
                   for idx in {j["mention_id"] for j in judgments}},
                  out)
    with open(WORK / "abstracts.json", "w") as out:
        json.dump({m["pmid"]: abstracts[m["pmid"]] for m in (mentions[i] for i in {j["mention_id"] for j in judgments})},
                  out)
    counts = defaultdict(int)
    for j in judgments:
        counts[j["status"]] += 1
    print(f"{len(judgments)} judgments: {dict(counts)}")
    print(f"{sum(len(v) for v in queue.values())} conflicts on {len(queue)} mentions to adjudicate -> {CONFLICTS}")


def replay_adjudications(path: Path = ADJUDICATIONS) -> dict[str, dict]:
    """
    Replays the append-only adjudication log: mention_id -> its latest record, either {"verdicts": {curie: ...}}
    or {"skipped": true}. An {"undo": true} record removes the mention's previous decision.
    """
    decisions = {}
    if path.exists():
        for line in path.read_text().splitlines():
            record = json.loads(line)
            if record.get("undo"):
                decisions.pop(record["mention_id"], None)
            else:
                decisions[record["mention_id"]] = record
    return decisions


def load_adjudications() -> dict[tuple[str, str], str]:
    """Decided verdict per (mention, CURIE): 'correct' | 'incorrect'. Skipped mentions are not decided."""
    return {(mention_id, curie): verdict for mention_id, record in replay_adjudications().items()
            for curie, verdict in record.get("verdicts", {}).items()}


def truth() -> None:
    judgments = [json.loads(line) for line in JUDGMENTS.read_text().splitlines()]
    mentions = json.loads((WORK / "mentions.json").read_text())
    abstracts = json.loads((WORK / "abstracts.json").read_text())
    adjudicated = load_adjudications()
    by_mention = defaultdict(list)
    unresolved = 0
    for j in judgments:
        status = j["status"]
        if status == "conflict":
            verdict = adjudicated.get((j["mention_id"], j["curie"]))
            if verdict is None:
                unresolved += 1
                continue
            status = f"adjudicated_{verdict}"
        if status in ("single", "unsure"):
            continue
        verdict, basis = status.split("_", 1)[1], status.split("_", 1)[0]
        by_mention[j["mention_id"]].append({
            "curie": j["curie"], "babel_id": j["babel_id"], "label": j["label"], "type": j["type"],
            "verdict": verdict, "basis": basis, "proposed_by": j["proposed_by"]})
    out_of_scope = [idx for idx in by_mention if mentions[idx]["mention_type"] in OUT_OF_SCOPE_TYPES
                    or mentions[idx]["medmentions_curie"] in OUT_OF_SCOPE_CONCEPTS]
    for idx in out_of_scope:
        del by_mention[idx]
    with open(TRUTH, "w") as out:
        for idx in sorted(by_mention, key=int):
            m = mentions[idx]
            out.write(json.dumps({"id": f"mm-assessed-{idx}", "pmid": m["pmid"], "text": abstracts[m["pmid"]],
                                  "mention": m["mention"], "expanded": m["expanded"],
                                  "mention_type": m["mention_type"], "medmentions_curie": m["medmentions_curie"],
                                  "judgments": by_mention[idx], "nodenorm_date": str(date.today())}) + "\n")
    n = sum(len(v) for v in by_mention.values())
    print(f"wrote {len(by_mention)} mentions / {n} judgments to {TRUTH}; left out {len(out_of_scope)} mentions of "
          f"out-of-scope types; {unresolved} conflicts not yet adjudicated")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare", help="read the bagel-eval dump; write the verdict table and adjudication queue")
    p.add_argument("--dump", type=Path, required=True)
    sub.add_parser("truth", help="combine concordant verdicts and adjudications into truth.jsonl")
    args = parser.parse_args()
    prepare(args.dump) if args.command == "prepare" else truth()


if __name__ == "__main__":
    main()
