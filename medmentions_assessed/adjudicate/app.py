"""
Local adjudication app for conflicting (mention, CURIE) assessments.

    uv run python medmentions_assessed/adjudicate/app.py      # then open http://127.0.0.1:8765

Shows one mention per screen: the abstract (mention highlighted), the mention string and the disputed terms.
Every decision is appended to medmentions_assessed/adjudications.jsonl immediately, so it can be stopped and
resumed at any time; the latest decision for a mention wins (which is also how undo works).
"""
import json
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from build import ADJUDICATIONS, ADJUDICATOR, CONFLICTS, replay_adjudications  # noqa: E402

PAGE = Path(__file__).with_name("index.html")
PORT = 8765


def load_queue() -> list[dict]:
    if not CONFLICTS.exists():
        sys.exit(f"{CONFLICTS} not found; run: uv run python medmentions_assessed/build.py prepare --dump <dump.sql>")
    return [json.loads(line) for line in CONFLICTS.read_text().splitlines()]


QUEUE = load_queue()
BY_ID = {item["mention_id"]: item for item in QUEUE}
DECISIONS = replay_adjudications()
HISTORY: list[str] = []  # mention ids decided in this session, for undo


def append(record: dict) -> None:
    record["time"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(ADJUDICATIONS, "a") as out:
        out.write(json.dumps(record) + "\n")


def next_item(after_skips: bool) -> dict | None:
    pending = [i for i in QUEUE if i["mention_id"] not in DECISIONS]
    if not pending and after_skips:
        pending = [i for i in QUEUE if DECISIONS.get(i["mention_id"], {}).get("skipped")]
    return pending[0] if pending else None


def progress() -> dict:
    decided = sum(1 for r in DECISIONS.values() if "verdicts" in r)
    skipped = sum(1 for r in DECISIONS.values() if r.get("skipped"))
    return {"decided": decided, "skipped": skipped, "total": len(QUEUE)}


class Handler(BaseHTTPRequestHandler):
    def _json(self, value, status=200):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            body = PAGE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/api/next"):
            self._json({"item": next_item(after_skips="skips=1" in self.path), "progress": progress()})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/api/decide":
            item = BY_ID[payload["mention_id"]]
            curies = [t["curie"] for t in item["terms"]]
            correct = set(payload["correct"])
            if not correct <= set(curies):
                return self._json({"error": "unknown CURIE"}, 400)
            record = {"mention_id": item["mention_id"], "adjudicator": ADJUDICATOR,
                      "verdicts": {c: ("correct" if c in correct else "incorrect") for c in curies}}
            append(dict(record))
            DECISIONS[item["mention_id"]] = record
            HISTORY.append(item["mention_id"])
        elif self.path == "/api/skip":
            record = {"mention_id": payload["mention_id"], "adjudicator": ADJUDICATOR, "skipped": True}
            append(dict(record))
            DECISIONS[payload["mention_id"]] = record
            HISTORY.append(payload["mention_id"])
        elif self.path == "/api/undo":
            if not HISTORY:
                return self._json({"item": None, "progress": progress()})
            mention_id = HISTORY.pop()
            append({"mention_id": mention_id, "adjudicator": ADJUDICATOR, "undo": True})
            DECISIONS.pop(mention_id, None)
            return self._json({"item": BY_ID[mention_id], "progress": progress()})
        else:
            return self._json({"error": "not found"}, 404)
        self._json({"item": next_item(after_skips=False), "progress": progress()})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print(f"{progress()['decided']}/{len(QUEUE)} decided; open http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
