#!/usr/bin/env python3
"""Focused checks: templates --json が指示型のプロンプトを ask として渡す。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "scripts" / "plaud-inbox"


def templates_json() -> list[dict]:
    r = subprocess.run(
        [str(INBOX), "templates", "--json"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def main() -> int:
    rows = {t["id"]: t for t in templates_json()}

    minutes = rows["meeting-minutes"]
    secs = minutes["sections"]
    assert len(secs) == 1, secs
    assert secs[0]["key"] == "本文"
    ask = secs[0]["ask"]
    assert "決定された事項" in ask
    assert "保留事項" in ask
    assert ask.strip() == Path(ROOT / "templates" / "meeting-minutes.md").read_text(encoding="utf-8").split("---", 2)[2].lstrip("\n").strip()

    notes = rows["meeting-notes"]
    keys = [s["key"] for s in notes["sections"]]
    assert "本文" not in keys
    assert "📝 会議ノート" in keys
    assert "📅 次の手配" in keys

    # 指示型は全部 本文 1キー
    instruction = [
        "detailed-summary",
        "medical-consultation",
        "meeting-minutes",
        "meeting-minutes-plus",
        "meeting-secretary",
        "voice-memo-notes",
    ]
    for tid in instruction:
        secs = rows[tid]["sections"]
        assert [s["key"] for s in secs] == ["本文"], (tid, secs)
        assert (secs[0]["ask"] or "").strip(), tid

    return 0


if __name__ == "__main__":
    sys.exit(main())
