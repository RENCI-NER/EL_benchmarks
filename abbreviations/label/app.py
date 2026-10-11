"""
Local app for labeling parentheticals in abbreviations/items.jsonl.

    uv run python abbreviations/label/app.py      # then open http://127.0.0.1:8766

Shows one parenthetical per screen, highlighted in its abstract. Each label is appended to abbreviations/labels.jsonl
at once, so labeling can stop and resume at any time; the latest record for an item wins, and undo appends a record
that removes the label.
"""
import json
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from build import DOCUMENTS, ITEMS, LABEL_VALUES, LABELS, replay_labels  # noqa: E402

PAGE = Path(__file__).with_name("index.html")
PORT = 8766

TEXTS = {d["id"]: d["text"] for d in map(json.loads, DOCUMENTS.read_text().splitlines())}
QUEUE = [json.loads(line) for line in ITEMS.read_text().splitlines()]
BY_ID = {item["id"]: item for item in QUEUE}
LABELED = replay_labels()
HISTORY: list[str] = []  # items labeled in this session, for undo


def append(record: dict) -> None:
    record["time"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(LABELS, "a") as out:
        out.write(json.dumps(record) + "\n")


def view(item: dict | None) -> dict | None:
    return None if item is None else {**item, "text": TEXTS[item["document"]]}


def next_item(after_skips: bool) -> dict | None:
    pending = [i for i in QUEUE if i["id"] not in LABELED]
    if not pending and after_skips:
        pending = [i for i in QUEUE if LABELED[i["id"]]["label"] == "skip"]
    return pending[0] if pending else None


def progress() -> dict:
    labels = [r["label"] for r in LABELED.values()]
    return {"labeled": sum(v in LABEL_VALUES for v in labels), "skipped": labels.count("skip"), "total": len(QUEUE),
            **{v: labels.count(v) for v in LABEL_VALUES}}


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
            self._json({"item": view(next_item(after_skips="skips=1" in self.path)), "progress": progress()})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/api/label":
            if payload["item"] not in BY_ID or payload["label"] not in (*LABEL_VALUES, "skip"):
                return self._json({"error": "unknown item or label"}, 400)
            record = {"item": payload["item"], "label": payload["label"]}
            append(dict(record))
            LABELED[payload["item"]] = record
            HISTORY.append(payload["item"])
        elif self.path == "/api/undo":
            if not HISTORY:
                return self._json({"item": view(next_item(after_skips=False)), "progress": progress()})
            item_id = HISTORY.pop()
            append({"item": item_id, "undo": True})
            LABELED.pop(item_id, None)
            return self._json({"item": view(BY_ID[item_id]), "progress": progress()})
        else:
            return self._json({"error": "not found"}, 404)
        self._json({"item": view(next_item(after_skips=False)), "progress": progress()})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print(f"{progress()['labeled']}/{len(QUEUE)} labeled; open http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
