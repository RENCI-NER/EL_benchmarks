"""
Builds the CRAFT linking benchmark from the CRAFT corpus (https://github.com/UCDenver-ccp/CRAFT, v5).

    python craft/build.py --craft ~/Projects/LitCoin/CRAFT [--sample 1000] [--seed 0]

Uses the core concept annotations for CHEBI, CL, GO (BP, CC, MF), NCBITaxon and UBERON, and MONDO without genotype
annotations. PR (species-agnostic protein classes), SO and MOP are left out, and so are the "+extensions" sets
(CRAFT-specific classes).

Each benchmark item is one mention occurrence: an article and its annotated spans, with the paragraph as context.
Its gold is every concept CRAFT annotated on exactly those spans. Items are deduplicated to one occurrence (the first)
per distinct (article, mention string), then sampled. Identifiers are CRAFT's own; MONDO IRIs are written as CURIEs,
a change of syntax only. Whether a linker's output matches is decided at evaluation time.
"""
import argparse
import json
import random
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
TRUTH = HERE / "truth.jsonl"
DOCUMENTS = HERE / "documents.jsonl"  # full article text, for document-level steps such as abbreviations
CORE = ["CHEBI", "CL", "GO_BP", "GO_CC", "GO_MF", "NCBITaxon", "UBERON"]  # knowtator format
MONDO = "MONDO/MONDO_without_genotype_annotations/knowtator-2"  # knowtator-2 format
OBO_PURL = re.compile(r"^http://purl\.obolibrary\.org/obo/([A-Za-z]+)_(.+)$")


def curie_of(class_id: str) -> str:
    """CRAFT class ids are CURIEs, except knowtator-2 files, which use OBO purls."""
    match = OBO_PURL.match(class_id)
    return f"{match.group(1)}:{match.group(2)}" if match else class_id


def read_knowtator(path: Path, ontology: str) -> list[dict]:
    """Annotations from a CRAFT knowtator XML file: [{"spans": [(start, end), ...], "curie", "ontology"}]."""
    root = ET.parse(path).getroot()
    classes = {cm.get("id"): cm.find("mentionClass").get("id") for cm in root.iter("classMention")}
    annotations = []
    for a in root.iter("annotation"):
        spans = [(int(s.get("start")), int(s.get("end"))) for s in a.iter("span")]
        annotations.append({"spans": spans, "curie": curie_of(classes[a.find("mention").get("id")]),
                            "ontology": ontology})
    return annotations


def read_knowtator2(path: Path, ontology: str) -> list[dict]:
    root = ET.parse(path).getroot()
    return [{"spans": [(int(s.get("start")), int(s.get("end"))) for s in a.iter("span")],
             "curie": curie_of(a.find("class").get("id")), "ontology": ontology}
            for a in root.iter("annotation")]


def load_annotations(craft: Path) -> dict[str, list[dict]]:
    """article id -> annotations from all included ontologies."""
    by_article = defaultdict(list)
    for ontology in CORE:
        for path in sorted((craft / "concept-annotation" / ontology / ontology / "knowtator").glob("*.xml")):
            by_article[path.name.split(".")[0]] += read_knowtator(path, ontology)
    for path in sorted((craft / "concept-annotation" / MONDO).glob("*.xml")):
        by_article[path.stem] += read_knowtator2(path, "MONDO")
    return by_article


def paragraph_bounds(text: str, offset: int) -> tuple[int, int]:
    """The line (CRAFT's paragraph unit in the txt files) containing offset."""
    start = text.rfind("\n", 0, offset) + 1
    end = text.find("\n", offset)
    return start, (len(text) if end == -1 else end)


def items(craft: Path) -> list[dict]:
    out = []
    for article, annotations in sorted(load_annotations(craft).items()):
        text = (craft / "articles" / "txt" / f"{article}.txt").read_text()
        gold = defaultdict(dict)  # spans -> {curie: ontology}
        for a in annotations:
            gold[tuple(a["spans"])][a["curie"]] = a["ontology"]
        seen = set()
        for spans in sorted(gold, key=lambda s: s[0]):
            mention = " ".join(text[s:e] for s, e in spans)
            if mention in seen:
                continue
            p_start, p_end = paragraph_bounds(text, spans[0][0])
            if spans[-1][1] > p_end:
                continue  # mentions spanning paragraphs (rare) have no single-paragraph context
            seen.add(mention)
            out.append({
                # the spans identify the occurrence; a start offset alone doesn't ("cell" and "cell line")
                "id": f"craft-{article}-" + "_".join(f"{s}-{e}" for s, e in spans), "article": article,
                "text": text[p_start:p_end],
                "mention": mention, "spans": [[s - p_start, e - p_start] for s, e in spans],
                "discontinuous": len(spans) > 1, "closed_world": True,
                "judgments": [{"curie": c, "verdict": "correct", "ontology": o} for c, o in sorted(gold[spans].items())],
            })
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--craft", type=Path, required=True, help="CRAFT repository checkout")
    parser.add_argument("--sample", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    everything = items(args.craft)
    ids = [i["id"] for i in everything]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate item ids")
    sample = sorted(random.Random(args.seed).sample(everything, args.sample), key=lambda i: i["id"])
    with open(TRUTH, "w") as out:
        for item in sample:
            out.write(json.dumps(item) + "\n")
    with open(DOCUMENTS, "w") as out:
        for article in sorted({i["article"] for i in sample}):
            out.write(json.dumps({"id": article, "text": (args.craft / "articles" / "txt" / f"{article}.txt").read_text()})
                      + "\n")
    print(f"{len(everything)} distinct (article, mention) items; wrote a sample of {len(sample)} to {TRUTH}")


if __name__ == "__main__":
    main()
