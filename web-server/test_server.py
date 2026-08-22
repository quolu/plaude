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
        segs = meeting["transcript"]
        assert segs and all(isinstance(s.get("t"), (int, float)) for s in segs)
        assert segs[0]["t"] == 0
        later = [s["t"] for s in segs if s["t"] > 0]
        assert later, segs
        assert meeting["summary"] and "熱中症" in meeting["summary"]
        st, body = fetch(f"{base}/api/templates")
        tpls = json.loads(body)
        assert any(t["id"] == "lecture" for t in tpls), tpls
        put = urllib.request.Request(
            f"{base}/api/templates/probe-crud",
            data=json.dumps({
                "title": "probe crud",
                "when": "試験用",
                "category": "一般",
                "body": "# 見出し\n本文",
            }).encode(),
            method="PUT",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(put, timeout=5) as r:
            saved = json.loads(r.read())
        assert saved["id"] == "probe-crud"
        assert "本文" in saved["body"]
        st, body = fetch(f"{base}/api/templates/probe-crud")
        got = json.loads(body)
        assert got["title"] == "probe crud"
        assert "本文" in got["body"]
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
        for leftover in (
            ROOT / "data" / "templates" / "probe-crud.md",
            ROOT / "data" / "meetings" / "probe-publish",
        ):
            if leftover.is_file():
                leftover.unlink()
            elif leftover.is_dir():
                import shutil
                shutil.rmtree(leftover, ignore_errors=True)
        httpd.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
