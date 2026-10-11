import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "medmentions_assessed"))
import build  # noqa: E402


def test_judgment_status():
    assert build.judgment_status({"a": "agree", "b": "agree"}) == "concordant_correct"
    assert build.judgment_status({"a": "disagree", "b": "disagree"}) == "concordant_incorrect"
    assert build.judgment_status({"a": "agree", "b": "disagree"}) == "conflict"
    assert build.judgment_status({"a": "agree"}) == "single"
    assert build.judgment_status({"a": "agree", "b": "unsure"}) == "unsure"


def test_copy_blocks_are_parsed_and_unescaped(tmp_path):
    dump = tmp_path / "dump.sql"
    dump.write_text("\n".join([
        "CREATE ROLE postgres;",
        "COPY public.recognized_entities (id, pmid, expanded_text, original_text) FROM stdin;",
        "7\t25763772\tcystic fibrosis\tCF",
        "8\t25763772\tlong\\ttab\\\\slash\t\\N",
        "\\.", ""]))
    rows = build.read_copy_tables(dump, tables=("recognized_entities",))["recognized_entities"]
    assert rows[0] == {"id": "7", "pmid": "25763772", "expanded_text": "cystic fibrosis", "original_text": "CF"}
    assert rows[1]["expanded_text"] == "long\ttab\\slash" and rows[1]["original_text"] is None


def test_adjudication_log_replay(tmp_path):
    log = tmp_path / "adjudications.jsonl"
    records = [
        {"mention_id": "1", "verdicts": {"A:1": "correct"}},
        {"mention_id": "1", "undo": True},
        {"mention_id": "1", "verdicts": {"A:1": "incorrect"}},
        {"mention_id": "2", "skipped": True},
        {"mention_id": "3", "verdicts": {"A:3": "correct"}},
        {"mention_id": "3", "undo": True},
    ]
    log.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    decisions = build.replay_adjudications(log)
    assert decisions["1"]["verdicts"] == {"A:1": "incorrect"}
    assert decisions["2"] == {"mention_id": "2", "skipped": True}
    assert "3" not in decisions


def test_scope_reasons_are_types_or_listed_concepts():
    assert "biolink:InformationContentEntity" in build.OUT_OF_SCOPE_TYPES
    assert all(c.startswith("UMLS:") for c in build.OUT_OF_SCOPE_CONCEPTS)


def test_truth_holds_only_source_identifiers():
    """The built benchmark must not carry Babel-derived identifiers or dates."""
    truth = build.TRUTH
    if not truth.exists():
        return
    for line in truth.read_text().splitlines()[:200]:
        record = json.loads(line)
        assert "nodenorm_date" not in record
        assert all(set(j) == {"curie", "label", "type", "verdict", "basis", "proposed_by"} for j in record["judgments"])
