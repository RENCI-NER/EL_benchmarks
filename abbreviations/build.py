"""
Builds the abbreviation-definition benchmark: parentheticals in held-out MedMentions abstracts, each labeled by
whether it defines an abbreviation for the same thing as the phrase next to it.

    python abbreviations/build.py sample --corpus <corpus_pubtator_normalized_8-4-2025.jsonl>
    python abbreviations/label/app.py          # label in the browser
    python abbreviations/build.py truth

`sample` draws 100 abstracts (seed 0) from the MedMentions corpus, leaving out those in medmentions_assessed, so
prompts can be developed without touching the linking benchmarks. The corpus file is BagelWithCheese's
tokenized copy of MedMentions (which is why the text reads "( CF )"). It writes documents.jsonl and items.jsonl.

An item is every parenthetical that follows whitespace and contains a letter, first occurrence per document and
contents. Labels:
- same: it, or the phrase it follows, is an abbreviation or symbol for the same thing as the other ("cystic
  fibrosis ( CF )", "IL1B ( Interleukin 1β )");
- instance: it names an example, member, level, strain or specific gene of the phrase ("K+ channel ( KCNJ10 )",
  "upper-thoracic ( T4 )");
- other: anything else (asides, statistics, citations, units).
"""
import argparse
import json
import random
import re
from pathlib import Path

HERE = Path(__file__).parent
DOCUMENTS = HERE / "documents.jsonl"
ITEMS = HERE / "items.jsonl"
LABELS = HERE / "labels.jsonl"
TRUTH = HERE / "truth.jsonl"
EXCLUDE = HERE.parent / "medmentions_assessed" / "documents.jsonl"
LABEL_VALUES = ("same", "instance", "other")


def parentheticals(text: str) -> list[dict]:
    """Top-level parentheticals following whitespace (not "Fe(III)"), containing a letter, first occurrence each."""
    found, seen, depth, open_at = [], set(), 0, None
    for i, char in enumerate(text):
        if char == "(":
            if depth == 0:
                if i > 0 and not text[i - 1].isspace():
                    continue
                open_at = i
            depth += 1
        elif char == ")" and depth > 0:
            depth -= 1
            if depth == 0:
                inner = text[open_at + 1:i].strip()
                if inner and inner not in seen and re.search(r"[A-Za-z]", inner):
                    seen.add(inner)
                    start = text.index(inner, open_at + 1)
                    found.append({"start": start, "end": start + len(inner), "inner": inner})
    return found


def sample(corpus: Path, n: int = 100, seed: int = 0) -> None:
    exclude = {json.loads(line)["id"] for line in EXCLUDE.read_text().splitlines()}
    docs = [json.loads(line) for line in corpus.read_text().splitlines()]
    docs = [{"id": str(d["pmid"]), "text": d["text"]} for d in docs if str(d["pmid"]) not in exclude]
    chosen = sorted(random.Random(seed).sample(docs, n), key=lambda d: int(d["id"]))
    with open(DOCUMENTS, "w") as out:
        for d in chosen:
            out.write(json.dumps(d) + "\n")
    count = 0
    with open(ITEMS, "w") as out:
        for d in chosen:
            for p in parentheticals(d["text"]):
                out.write(json.dumps({"id": f"{d['id']}-{p['start']}", "document": d["id"], **p}) + "\n")
                count += 1
    print(f"wrote {len(chosen)} abstracts to {DOCUMENTS} and {count} parentheticals to {ITEMS}")


def replay_labels(path: Path = LABELS) -> dict[str, dict]:
    """item id -> latest record; an undo record removes the item's label."""
    latest = {}
    if path.exists():
        for record in map(json.loads, path.read_text().splitlines()):
            if record.get("undo"):
                latest.pop(record["item"], None)
            else:
                latest[record["item"]] = record
    return latest


def truth() -> None:
    labels = replay_labels()
    items = [json.loads(line) for line in ITEMS.read_text().splitlines()]
    labeled = [i for i in items if labels.get(i["id"], {}).get("label") in LABEL_VALUES]
    with open(TRUTH, "w") as out:
        for item in labeled:
            out.write(json.dumps({**item, "label": labels[item["id"]]["label"]}) + "\n")
    counts = {v: sum(labels[i["id"]]["label"] == v for i in labeled) for v in LABEL_VALUES}
    print(f"wrote {len(labeled)} of {len(items)} items to {TRUTH}: {counts}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("sample", help="sample abstracts and list their parentheticals")
    p.add_argument("--corpus", type=Path, required=True)
    sub.add_parser("truth", help="write truth.jsonl from labels.jsonl")
    args = parser.parse_args()
    sample(args.corpus) if args.command == "sample" else truth()


if __name__ == "__main__":
    main()
