#!/usr/bin/env python3
"""SSH投函・Windows形式のパス・失敗時の保留を確認する。"""
import json
import os
import tempfile
from pathlib import Path
from test_plaud_inbox_publish import fake_worker, seed_audio, run_transcribe


def main():
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        bindir, log = fake_worker(root)
        config = root / "config.json"
        config.write_text(json.dumps({"data_dir": str(root / "data"), "asr_host": "fake-worker", "asr_engine": "whisper"}))
        env = os.environ | {"PATH": f"{bindir}:{os.environ['PATH']}", "FAKE_LOG": str(log),
            "FAKE_RESULT": json.dumps({"schema":"asr-worker.result.v2", "engine":"whisper", "diarizer":"pyannote", "speakers":["Speaker 1","Speaker 2"], "segments":[{"t":1,"speaker":"Speaker 1","text":"日本語の転写"},{"t":3,"speaker":"Speaker 2","text":"話者交代"}]})}
        state = seed_audio(root, "success")
        result = run_transcribe(config, "success", env)
        assert result.returncode == 0, result.stderr
        rec = json.loads(state.read_text())["files"]["success"]
        assert Path(rec["transcript"]).read_text(encoding="utf-8") == "[00:01 Speaker 1]\n日本語の転写\n[00:03 Speaker 2]\n話者交代\n"
        calls = log.read_text()
        assert "~/asr/bin/asr-worker prepare success" in calls
        assert "C:/Users/kite_/asr/inbox/success/audio.mp3" in calls
        assert "C:/Users/kite_/asr/jobs/success/result.json" in calls
        assert "mkdir" not in calls and "cat ~/" not in calls
        for fid, extras, code in [
            ("failed", {"FAKE_STATUS":'{"status":"failed","reason":"GPU失敗"}'}, "TRANSCRIBE_WORKER_FAILED"),
            ("unreachable", {"FAKE_SSH_UNREACHABLE":"1"}, "TRANSCRIBE_WORKER_UNREACHABLE"),
            ("legacy", {"FAKE_RESULT":'{"schema":"asr-worker.result.v1","segments":[]}'}, "TRANSCRIBE_WORKER_INVALID_RESULT"),
            ("unknown", {"FAKE_STATUS":'{"status":"unknown"}'}, "TRANSCRIBE_WORKER_PROTOCOL_ERROR")]:
            state = seed_audio(root, fid)
            result = run_transcribe(config, fid, env | extras)
            assert result.returncode == 1
            rec = json.loads(state.read_text())["files"][fid]
            assert "transcribed_at" not in rec and "completed_at" not in rec
            assert rec["transcribe_error"]["code"] == code
    print("worker: 5件の確認に成功")


if __name__ == "__main__":
    main()
