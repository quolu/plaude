#!/usr/bin/env python3
"""Focused checks for plaud-inbox publish completion semantics."""
from __future__ import annotations

import json
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "scripts" / "plaud-inbox"


class PublishHandler(BaseHTTPRequestHandler):
    status = 200
    received: list[dict] = []

    def log_message(self, fmt, *args):
        pass

    def do_POST(self):
        assert self.path == "/api/publish"
        size = int(self.headers["Content-Length"])
        self.received.append(json.loads(self.rfile.read(size)))
        body = b'{"ok":true}\n'
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_publish(config: Path, fid: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(INBOX), "--config", str(config), "publish", fid],
        text=True,
        capture_output=True,
        check=False,
    )


def configure(root: Path, origin: str) -> Path:
    config = root / "config.json"
    config.write_text(json.dumps({"data_dir": str(root / "data"), "site_origin": origin}), encoding="utf-8")
    return config


def seed(root: Path, fid: str) -> Path:
    data = root / "data"
    (data / "transcripts").mkdir(parents=True, exist_ok=True)
    (data / "notes").mkdir(exist_ok=True)
    transcript = data / "transcripts" / f"{fid}.txt"
    transcript.write_text("一行目\n二行目\n", encoding="utf-8")
    (data / "notes" / f"{fid}.md").write_text("# 要約\n内容\n", encoding="utf-8")
    (data / "state.json").write_text(
        json.dumps({"files": {fid: {
            "name": "公開テスト",
            "start_at": "2026-08-22T10:00:00+09:00",
            "duration_ms": 6000,
            "template": "meeting",
            "transcript": str(transcript),
            "audio_url": "https://audio.example.test/recording.mp3",
        }}}),
        encoding="utf-8",
    )
    return data / "state.json"


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 0), PublishHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://{server.server_address[0]}:{server.server_address[1]}"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = configure(root, origin)
            state = seed(root, "ok")
            assert json.loads((ROOT / "config.example.json").read_text())["steps"]["mail"] is False

            PublishHandler.status = 200
            result = run_publish(config, "ok")
            assert result.returncode == 0, result.stderr
            payload = PublishHandler.received[-1]
            assert payload["id"] == "ok"
            assert payload["title"] == "公開テスト"
            assert payload["template_id"] == "meeting"
            assert payload["transcript"] == [
                {"t": 0, "speaker": "Speaker 1", "text": "一行目\n二行目"}
            ]
            assert payload["summary"] == "# 要約\n内容\n"
            assert payload["audio_url"] == "https://audio.example.test/recording.mp3"
            complete = json.loads(state.read_text())["files"]["ok"]
            assert complete["published_at"] == complete["completed_at"]

            failed_state = seed(root, "failed")
            PublishHandler.status = 500
            result = run_publish(config, "failed")
            assert result.returncode == 1
            failed = json.loads(failed_state.read_text())["files"]["failed"]
            assert "published_at" not in failed and "completed_at" not in failed

            unreachable_state = seed(root, "unreachable")
            unreachable_config = configure(root, "http://127.0.0.1:1")
            result = run_publish(unreachable_config, "unreachable")
            assert result.returncode == 1
            unreachable = json.loads(unreachable_state.read_text())["files"]["unreachable"]
            assert "published_at" not in unreachable and "completed_at" not in unreachable
    finally:
        server.shutdown()
        server.server_close()
    print("plaud-inbox publish checks ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
