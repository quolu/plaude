#!/usr/bin/env python3
"""plaud.kitepon.dev origin: meetings + templates + static."""
from __future__ import annotations

import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = Path(os.environ.get("PLAUDE_DATA_DIR") or (ROOT / "data"))
STATIC_DIR = Path(os.environ.get("PLAUDE_STATIC_DIR") or (ROOT / "web" / "dist"))
PUBLISH_TOKEN = os.environ.get("PLAUDE_PUBLISH_TOKEN") or ""


def meeting_dir(data: Path, mid: str) -> Path:
    if not re.fullmatch(r"[0-9A-Za-z._-]{1,128}", mid):
        raise ValueError("bad id")
    return data / "meetings" / mid


def load_meeting(data: Path, mid: str) -> dict | None:
    d = meeting_dir(data, mid)
    meta_p = d / "meta.json"
    if not meta_p.is_file():
        return None
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    tr_p = d / "transcript.json"
    transcript = json.loads(tr_p.read_text(encoding="utf-8")) if tr_p.is_file() else []
    sum_md = d / "summary.md"
    sum_json = d / "summary.json"
    summary_text = sum_md.read_text(encoding="utf-8") if sum_md.is_file() else ""
    summary_obj = json.loads(sum_json.read_text(encoding="utf-8")) if sum_json.is_file() else None
    if summary_obj and not summary_text:
        summary_text = summary_obj.get("summary") or ""
    audio = d / "audio.mp3"
    return {
        "id": mid,
        "title": meta.get("title") or meta.get("name") or mid,
        "started_at": meta.get("started_at") or meta.get("start_at") or "",
        "duration": meta.get("duration") or "",
        "duration_ms": meta.get("duration_ms"),
        "template_id": meta.get("template_id"),
        "has_audio": audio.is_file(),
        "transcript": transcript,
        "summary": summary_text,
        "summary_struct": summary_obj,
    }


def list_meetings(data: Path) -> list[dict]:
    root = data / "meetings"
    if not root.is_dir():
        return []
    rows = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        m = load_meeting(data, child.name)
        if not m:
            continue
        rows.append(
            {
                "id": m["id"],
                "title": m["title"],
                "started_at": m["started_at"],
                "duration": m["duration"],
                "duration_ms": m["duration_ms"],
            }
        )
    rows.sort(key=lambda r: r.get("started_at") or "", reverse=True)
    return rows


def parse_template(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    meta = {"id": path.stem, "title": path.stem, "when": "", "category": "", "source": "", "author": "", "body": text}
    if text.startswith("---"):
        _, fm, body = text.split("---", 2)
        meta["body"] = body.lstrip("\n")
        for line in fm.splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta


def list_templates(data: Path, skill_templates: Path) -> list[dict]:
    seen: dict[str, dict] = {}
    for folder in (skill_templates, data / "templates"):
        if not folder.is_dir():
            continue
        for p in sorted(folder.glob("*.md")):
            t = parse_template(p)
            seen[t["id"]] = {
                "id": t["id"],
                "title": t["title"],
                "when": t["when"],
                "category": t.get("category") or "",
                "source": t.get("source") or "",
                "author": t.get("author") or "",
                "body": t["body"],
            }
    return list(seen.values())


def write_template(data: Path, tid: str, payload: dict) -> dict:
    if not re.fullmatch(r"[0-9A-Za-z._-]{1,128}", tid):
        raise ValueError("bad id")
    folder = data / "templates"
    folder.mkdir(parents=True, exist_ok=True)
    title = payload.get("title") or tid
    when = payload.get("when") or ""
    category = payload.get("category") or ""
    body = payload.get("body") or ""
    text = (
        f"---\nid: {tid}\ntitle: {title}\nwhen: {when}\ncategory: {category}\n"
        f"source: {payload.get('source') or 'custom'}\nauthor: {payload.get('author') or ''}\n---\n"
        f"{body.rstrip()}\n"
    )
    (folder / f"{tid}.md").write_text(text, encoding="utf-8")
    return parse_template(folder / f"{tid}.md")


def save_meeting(data: Path, mid: str, payload: dict) -> dict:
    d = meeting_dir(data, mid)
    d.mkdir(parents=True, exist_ok=True)
    meta = {
        "id": mid,
        "title": payload.get("title") or payload.get("name") or mid,
        "started_at": payload.get("started_at") or payload.get("start_at") or "",
        "duration": payload.get("duration") or "",
        "duration_ms": payload.get("duration_ms"),
        "template_id": payload.get("template_id"),
    }
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if "transcript" in payload:
        (d / "transcript.json").write_text(
            json.dumps(payload["transcript"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if "summary" in payload and isinstance(payload["summary"], str):
        (d / "summary.md").write_text(payload["summary"] if payload["summary"].endswith("\n") else payload["summary"] + "\n", encoding="utf-8")
    if "summary_struct" in payload and payload["summary_struct"] is not None:
        (d / "summary.json").write_text(
            json.dumps(payload["summary_struct"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return load_meeting(data, mid)


def make_handler(data: Path, static_dir: Path, skill_templates: Path, token: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

        def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _send_audio(self, path: Path):
            body = path.read_bytes()
            extra = {"Accept-Ranges": "bytes"}
            rng = self.headers.get("Range") or ""
            if rng.startswith("bytes="):
                spec = rng.split("=", 1)[1]
                start_s, _, end_s = spec.partition("-")
                start = int(start_s) if start_s else 0
                end = int(end_s) if end_s else len(body) - 1
                start = max(0, start)
                end = min(len(body) - 1, end)
                chunk = body[start : end + 1]
                extra["Content-Range"] = f"bytes {start}-{end}/{len(body)}"
                self._send(206, chunk, "audio/mpeg", extra)
                return
            self._send(200, body, "audio/mpeg", extra)

        def _json(self, code: int, obj):
            raw = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
            self._send(code, raw, "application/json; charset=utf-8")

        def _read_json(self):
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n).decode("utf-8") or "{}")

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/healthz":
                self._send(200, b"ok\n", "text/plain; charset=utf-8")
                return
            if path == "/api/meetings":
                self._json(200, list_meetings(data))
                return
            m = re.fullmatch(r"/api/meetings/([^/]+)", path)
            if m:
                meeting = load_meeting(data, m.group(1))
                if not meeting:
                    self._json(404, {"error": "not found"})
                    return
                self._json(200, meeting)
                return
            m = re.fullmatch(r"/m/([^/]+)/audio", path)
            if m:
                audio = meeting_dir(data, m.group(1)) / "audio.mp3"
                if not audio.is_file():
                    self._json(404, {"error": "no audio"})
                    return
                self._send_audio(audio)
                return
            if path == "/api/templates":
                self._json(200, list_templates(data, skill_templates))
                return
            m = re.fullmatch(r"/api/templates/([^/]+)", path)
            if m:
                rows = {t["id"]: t for t in list_templates(data, skill_templates)}
                if m.group(1) not in rows:
                    self._json(404, {"error": "not found"})
                    return
                self._json(200, rows[m.group(1)])
                return
            self._static(path)

        def do_PUT(self):
            parsed = urlparse(self.path)
            m = re.fullmatch(r"/api/templates/([^/]+)", parsed.path)
            if not m:
                self._json(404, {"error": "not found"})
                return
            try:
                saved = write_template(data, m.group(1), self._read_json())
            except ValueError:
                self._json(400, {"error": "bad id"})
                return
            self._json(200, saved)

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path != "/api/publish":
                self._json(404, {"error": "not found"})
                return
            got = self.headers.get("Authorization") or ""
            if token and got != f"Bearer {token}":
                self._json(401, {"error": "unauthorized"})
                return
            payload = self._read_json()
            mid = payload.get("id")
            if not mid:
                self._json(400, {"error": "id required"})
                return
            saved = save_meeting(data, mid, payload)
            self._json(200, saved)

        def _static(self, path: str):
            if path == "/":
                path = "/index.html"
            target = (static_dir / path.lstrip("/")).resolve()
            try:
                target.relative_to(static_dir.resolve())
            except ValueError:
                self._json(404, {"error": "not found"})
                return
            if not target.is_file():
                spa = static_dir / "index.html"
                if spa.is_file() and not path.startswith("/api"):
                    body = spa.read_bytes()
                    self._send(200, body, "text/html; charset=utf-8")
                    return
                self._json(404, {"error": "not found"})
                return
            ctype = "text/plain; charset=utf-8"
            if target.suffix == ".html":
                ctype = "text/html; charset=utf-8"
            elif target.suffix == ".js":
                ctype = "text/javascript; charset=utf-8"
            elif target.suffix == ".css":
                ctype = "text/css; charset=utf-8"
            elif target.suffix == ".svg":
                ctype = "image/svg+xml"
            self._send(200, target.read_bytes(), ctype)

    return Handler


def serve(host: str, port: int, data: Path | None = None):
    data = data or DEFAULT_DATA
    data.mkdir(parents=True, exist_ok=True)
    handler = make_handler(data, STATIC_DIR, ROOT / "templates", PUBLISH_TOKEN)
    httpd = ThreadingHTTPServer((host, port), handler)
    return httpd


def main() -> int:
    host = os.environ.get("PLAUDE_BIND") or "127.0.0.1"
    port = int(os.environ.get("PLAUDE_PORT") or "18880")
    httpd = serve(host, port)
    print(f"plaude origin http://{host}:{port}", flush=True)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
