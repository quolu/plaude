#!/usr/bin/env python3
import json
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import urllib.request
from pathlib import Path

from server import serve

ROOT = Path(__file__).resolve().parent.parent


class QuietStaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass


def audio_source():
    tmp = tempfile.TemporaryDirectory()
    audio = Path(tmp.name) / "recording.mp3"
    audio.write_bytes(b"ID3" + b"test-audio" * 8)
    handler = lambda *args, **kwargs: QuietStaticHandler(*args, directory=tmp.name, **kwargs)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return tmp, httpd, f"http://{httpd.server_address[0]}:{httpd.server_address[1]}/recording.mp3", audio.read_bytes()


def fetch(url: str):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, r.headers, r.read()


def main() -> int:
    source_tmp, source_httpd, audio_url, expected_audio = audio_source()
    httpd = serve("127.0.0.1", 0, ROOT / "data")
    host, port = httpd.server_address[:2]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://{host}:{port}"
    try:
        st, _, body = fetch(f"{base}/healthz")
        assert st == 200 and body.strip() == b"ok", (st, body)
        st, _, body = fetch(f"{base}/api/meetings")
        rows = json.loads(body)
        assert isinstance(rows, list) and any(r["id"] == "mock-safety" for r in rows), rows
        st, _, body = fetch(f"{base}/api/meetings/mock-safety")
        meeting = json.loads(body)
        assert meeting["title"]
        assert meeting["duration"]
        segs = meeting["transcript"]
        assert segs and all(isinstance(s.get("t"), (int, float)) for s in segs)
        assert segs[0]["t"] == 0
        later = [s["t"] for s in segs if s["t"] > 0]
        assert later, segs
        assert meeting["summary"] and "熱中症" in meeting["summary"]
        assert meeting["has_audio"] is True
        st, headers, body = fetch(f"{base}/m/mock-safety/audio")
        assert st == 200 and headers.get_content_type() == "audio/mpeg" and len(body) > 0
        ranged = urllib.request.Request(
            f"{base}/m/mock-safety/audio",
            headers={"Range": "bytes=0-31"},
        )
        with urllib.request.urlopen(ranged, timeout=5) as r:
            assert r.status == 206
            assert r.headers.get_content_type() == "audio/mpeg"
            assert r.headers["Accept-Ranges"] == "bytes"
            assert r.headers["Content-Range"].startswith("bytes 0-31/")
            assert len(r.read()) == 32
        st, _, body = fetch(f"{base}/api/templates")
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
        st, _, body = fetch(f"{base}/api/templates/probe-crud")
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
                "transcript": [{"t": 0, "text": "hi"}, {"t": 5, "text": "next"}],
                "summary": "短い試験",
                "phases": [{"t": 0, "title": "冒頭"}, {"t": 5, "title": "本題"}],
                "audio_url": audio_url,
            }).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            published = json.loads(r.read())
        assert published["title"] == "probe"
        assert published["has_audio"] is True
        assert published["phases"] == [{"t": 0, "title": "冒頭"}, {"t": 5, "title": "本題"}]
        st, headers, body = fetch(f"{base}/m/probe-publish/audio")
        assert st == 200 and headers.get_content_type() == "audio/mpeg" and body == expected_audio
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
        source_httpd.shutdown()
        source_httpd.server_close()
        source_tmp.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
