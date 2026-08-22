#!/usr/bin/env python3
"""Focused checks for plaud-inbox publish completion semantics."""
from __future__ import annotations

import json
import os
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


def run_transcribe(config: Path, fid: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(INBOX), "--config", str(config), "transcribe", fid],
        text=True,
        capture_output=True,
        check=False,
        env=env,
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


def seed_audio(root: Path, fid: str) -> Path:
    data = root / "data"
    (data / "audio").mkdir(parents=True, exist_ok=True)
    audio = data / "audio" / f"{fid}.mp3"
    audio.write_bytes(b"fake audio")
    state = data / "state.json"
    state.write_text(json.dumps({"files": {fid: {"audio": str(audio), "pulled_at": "2026-08-22T00:00:00+00:00"}}}), encoding="utf-8")
    return state


def fake_worker(root: Path) -> tuple[Path, Path]:
    bindir = root / "bin"
    bindir.mkdir(parents=True)
    log = root / "worker-calls.jsonl"
    (bindir / "ssh").write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "from pathlib import Path\n"
        "Path(os.environ['FAKE_LOG']).open('a').write('ssh ' + repr(sys.argv[1:]) + '\\n')\n"
        "if os.environ.get('FAKE_SSH_UNREACHABLE') == '1':\n"
        "    print('connection refused', file=sys.stderr); raise SystemExit(255)\n"
        "if 'cat ~/asr/jobs/' in sys.argv[-1]: print(os.environ.get('FAKE_STATUS', '{\\\"status\\\": \\\"done\\\"}'))\n",
        encoding="utf-8",
    )
    (bindir / "scp").write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "from pathlib import Path\n"
        "Path(os.environ['FAKE_LOG']).open('a').write('scp ' + repr(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1].startswith('fake-worker:~/asr/jobs/'):\n"
        "    Path(sys.argv[2]).write_text(os.environ['FAKE_RESULT'], encoding='utf-8')\n",
        encoding="utf-8",
    )
    for command in (bindir / "ssh", bindir / "scp"):
        command.chmod(0o755)
    return bindir, log


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

            segments = [
                {"t": 12.34, "speaker": "Speaker 1", "text": "時刻付き"},
                {"t": 56.78, "speaker": "Speaker 1", "text": "透過する"},
            ]
            json_state = seed(root, "json")
            result_path = root / "data" / "transcripts" / "json.json"
            result_path.write_text(json.dumps({"schema": "asr-worker.result.v1", "segments": segments}), encoding="utf-8")
            json_data = json.loads(json_state.read_text())
            json_data["files"]["json"]["transcript_json"] = str(result_path)
            json_state.write_text(json.dumps(json_data), encoding="utf-8")
            result = run_publish(config, "json")
            assert result.returncode == 0, result.stderr
            assert PublishHandler.received[-1]["transcript"] == segments

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

            worker_root = root / "worker"
            bindir, log = fake_worker(worker_root)
            worker_config = configure(worker_root, origin)
            worker_config.write_text(json.dumps({
                "data_dir": str(worker_root / "data"),
                "site_origin": origin,
                "asr_host": "fake-worker",
                "asr_engine": "parakeet",
            }), encoding="utf-8")
            worker_state = seed_audio(worker_root, "worker-ok")
            worker_env = os.environ | {
                "PATH": f"{bindir}:{os.environ['PATH']}",
                "FAKE_LOG": str(log),
                "FAKE_RESULT": json.dumps({
                    "schema": "asr-worker.result.v1",
                    "engine": "parakeet",
                    "segments": segments,
                }),
            }
            result = run_transcribe(worker_config, "worker-ok", worker_env)
            assert result.returncode == 0, result.stderr
            worker = json.loads(worker_state.read_text())["files"]["worker-ok"]
            assert worker["engine"] == "parakeet"
            assert worker["transcribed_at"]
            assert Path(worker["transcript_json"]).exists()
            assert Path(worker["transcript"]).read_text(encoding="utf-8") == "時刻付き\n透過する\n"
            calls = log.read_text(encoding="utf-8")
            assert "~/asr/inbox/worker-ok/audio.mp3" in calls
            assert "submit worker-ok --engine parakeet" in calls
            assert "~/asr/jobs/worker-ok/result.json" in calls

            failed_worker_state = seed_audio(worker_root, "worker-failed")
            result = run_transcribe(worker_config, "worker-failed", worker_env | {
                "FAKE_STATUS": json.dumps({"status": "failed", "reason": "decoder failure"}),
            })
            assert result.returncode == 1
            failed_worker = json.loads(failed_worker_state.read_text())["files"]["worker-failed"]
            assert "transcribed_at" not in failed_worker
            assert failed_worker["transcribe_error"]["code"] == "TRANSCRIBE_WORKER_FAILED"

            unreachable_worker_state = seed_audio(worker_root, "worker-unreachable")
            result = run_transcribe(worker_config, "worker-unreachable", worker_env | {"FAKE_SSH_UNREACHABLE": "1"})
            assert result.returncode == 1
            unreachable_worker = json.loads(unreachable_worker_state.read_text())["files"]["worker-unreachable"]
            assert "transcribed_at" not in unreachable_worker
            assert unreachable_worker["transcribe_error"]["code"] == "TRANSCRIBE_WORKER_UNREACHABLE"
    finally:
        server.shutdown()
        server.server_close()
    print("plaud-inbox publish checks ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
