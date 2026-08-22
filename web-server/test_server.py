#!/usr/bin/env python3
import json
import threading
import urllib.request
from pathlib import Path

from server import serve

ROOT = Path(__file__).resolve().parent.parent


def fetch(url: str):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, r.read()


def main() -> int:
    httpd = serve("127.0.0.1", 0, ROOT / "data")
    host, port = httpd.server_address[:2]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://{host}:{port}"
    try:
        st, body = fetch(f"{base}/healthz")
        assert st == 200 and body.strip() == b"ok", (st, body)
        st, body = fetch(f"{base}/api/meetings")
        rows = json.loads(body)
        assert isinstance(rows, list) and any(r["id"] == "mock-safety" for r in rows), rows
        st, body = fetch(f"{base}/api/meetings/mock-safety")
        meeting = json.loads(body)
        assert meeting["title"]
        assert meeting["duration"]
        assert meeting["transcript"] and isinstance(meeting["transcript"][0]["t"], (int, float))
        assert meeting["summary"] and "熱中症" in meeting["summary"]
        req = urllib.request.Request(
            f"{base}/api/publish",
            data=json.dumps({
                "id": "probe-publish",
                "title": "probe",
                "started_at": "2026-08-22T00:00:00",
                "duration": "6秒",
                "transcript": [{"t": 0, "text": "hi"}],
                "summary": "短い試験",
            }).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            published = json.loads(r.read())
        assert published["title"] == "probe"
        print("origin probes ok", meeting["title"])
        return 0
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
