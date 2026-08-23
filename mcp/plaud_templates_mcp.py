#!/usr/bin/env python3
"""Plaud テンプレコミュニティ抽出 MCP（stdio・標準ライブラリのみ）。

web.plaud.ai のテンプレコミュニティから、公式テンプレの骨組み
（pre_markdown）とコミュニティテンプレの原文（content）を取り出す。
公式の開発者 API・公式 MCP はテンプレ取得を持たない（2026-08-23 調査）ため、
Web アプリの内部 API を Bearer トークンで叩く。

認証: web.plaud.ai ログイン中の Authorization Bearer 値を
~/.config/plaud-templates/token へ保存する（約1日で失効）。
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = os.environ.get("PLAUD_API_BASE") or "https://api-apne1.plaud.ai"
TOKEN_PATH = Path(os.environ.get("PLAUD_WEB_TOKEN_FILE") or "~/.config/plaud-templates/token").expanduser()
TOKEN_HINT = (
    f"web.plaud.ai へログインし、開発者ツールの Network で任意の api-apne1.plaud.ai リクエストの "
    f"Authorization ヘッダ（Bearer ...）をコピーして {TOKEN_PATH} へ保存する。約1日で失効する。"
)


def token() -> str:
    value = os.environ.get("PLAUD_WEB_TOKEN") or (
        TOKEN_PATH.read_text(encoding="utf-8").strip() if TOKEN_PATH.is_file() else ""
    )
    if not value:
        raise RuntimeError(f"トークンが無い。{TOKEN_HINT}")
    return value if value.startswith("Bearer ") else f"Bearer {value}"


def api(path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method="POST" if payload is not None else "GET",
        headers={
            "Authorization": token(),
            "Content-Type": "application/json",
            "User-Agent": "plaud-templates-mcp/1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API {e.code}: トークン失効の可能性。{TOKEN_HINT}") from e
    if body.get("status") != 0:
        raise RuntimeError(f"API error: {body.get('msg')}")
    return body


def home(language: str) -> list[dict]:
    return api("/summary/community/templates/home", {"language_os": language})["data"]


def tool_categories(language: str = "ja") -> list[dict]:
    return [
        {"category_id": c["category_id"], "name": c["category_name"], "total": c["category_total_nums"]}
        for c in home(language)
    ]


def tool_official(category_id: str | None = None, language: str = "ja") -> list[dict]:
    out = []
    for cat in home(language):
        if category_id and cat["category_id"] != category_id:
            continue
        for item in cat["data"]:
            tpl = item.get("template")
            if not tpl or not tpl.get("pre_markdown"):
                continue  # コミュニティ枠や骨組み無しは対象外
            out.append({
                "category_id": cat["category_id"],
                "name": tpl.get("name"),
                "description": tpl.get("description_long") or tpl.get("description_short"),
                "locked": bool(tpl.get("is_locked")),
                "pre_markdown": tpl["pre_markdown"],
            })
    return out


def community_page(category_id: str, page: int, page_size: int, language: str) -> list[dict]:
    body = api(
        f"/summary/chatllm/templates?language_os={language}&has_recently_use=false&has_custom=false"
        f"&category_id={category_id}&page={page}&page_size={page_size}"
    )
    rows = []
    for group in body.get("templates", []):
        for t in group.get("community_templates") or []:
            v = t.get("latest_published_version") or {}
            rows.append({
                "id": t["id"],
                "author": t.get("author_name"),
                "locked": bool(t.get("is_locked")),
                "title": v.get("note_tab_name") or v.get("description_short"),
                "description": v.get("description_long") or v.get("description_short"),
                "content": v.get("content"),
            })
    return rows


def tool_community_list(category_id: str, page: int = 1, page_size: int = 12, language: str = "ja") -> list[dict]:
    rows = community_page(category_id, page, page_size, language)
    return [{k: r[k] for k in ("id", "title", "author", "description", "locked")} for r in rows]


def tool_get(category_id: str, template_id: str, language: str = "ja", max_pages: int = 40) -> dict:
    for page in range(1, max_pages + 1):
        rows = community_page(category_id, page, 50, language)
        if not rows:
            break
        for r in rows:
            if r["id"] == template_id:
                return r
    raise RuntimeError(f"テンプレ {template_id} が {category_id} の先頭 {max_pages * 50} 件に見つからない")


TOOLS = [
    {
        "name": "plaud_template_categories",
        "description": "Plaud テンプレコミュニティのカテゴリ一覧（id・名前・件数）を返す。",
        "inputSchema": {"type": "object", "properties": {
            "language": {"type": "string", "description": "表示言語（既定 ja）"}}},
    },
    {
        "name": "plaud_official_templates",
        "description": "Plaud 公式テンプレの骨組み（pre_markdown 原文）を返す。category_id で絞り込み可。",
        "inputSchema": {"type": "object", "properties": {
            "category_id": {"type": "string"},
            "language": {"type": "string", "description": "表示言語（既定 ja）"}}},
    },
    {
        "name": "plaud_community_templates",
        "description": "コミュニティテンプレの一覧（id・題名・作者・説明）をカテゴリとページ指定で返す。本文は plaud_community_template_get で取る。",
        "inputSchema": {"type": "object", "required": ["category_id"], "properties": {
            "category_id": {"type": "string"},
            "page": {"type": "integer"},
            "page_size": {"type": "integer"},
            "language": {"type": "string"}}},
    },
    {
        "name": "plaud_community_template_get",
        "description": "コミュニティテンプレ1件の原文（content・原語のまま）とメタ情報を返す。",
        "inputSchema": {"type": "object", "required": ["category_id", "template_id"], "properties": {
            "category_id": {"type": "string"},
            "template_id": {"type": "string"},
            "language": {"type": "string"}}},
    },
]

HANDLERS = {
    "plaud_template_categories": lambda a: tool_categories(**a),
    "plaud_official_templates": lambda a: tool_official(**a),
    "plaud_community_templates": lambda a: tool_community_list(**a),
    "plaud_community_template_get": lambda a: tool_get(**a),
}


def reply(msg_id, result=None, error=None) -> None:
    out: dict = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        out["error"] = error
    else:
        out["result"] = result
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        method, msg_id = msg.get("method"), msg.get("id")
        if method == "initialize":
            reply(msg_id, {
                "protocolVersion": msg.get("params", {}).get("protocolVersion", "2024-11-05"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "plaud-templates", "version": "0.1.0"},
            })
        elif method == "tools/list":
            reply(msg_id, {"tools": TOOLS})
        elif method == "tools/call":
            name = msg["params"]["name"]
            args = msg["params"].get("arguments") or {}
            try:
                result = HANDLERS[name](args)
                reply(msg_id, {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=1)}]})
            except Exception as e:
                reply(msg_id, {"content": [{"type": "text", "text": str(e)}], "isError": True})
        elif msg_id is not None:
            reply(msg_id, error={"code": -32601, "message": f"unknown method: {method}"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
