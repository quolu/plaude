# plaud.kitepon.dev — 会議ごとの文字起こし／要約ページ

この計画の正本は **Developer/plaude**。YuiHome では作業しない。GitHub は [quolu/plaude](https://github.com/quolu/plaude)。

GrokBot の取り込み結果を、公式 Plaud 共有ページと同じ情報面で出す。

参照した公式面（安全教育 1時間34分）:

- タブ **文字起こし** / **要約**
- 上段: タイトル、日時、長さ、音声プレイヤー（再生・シーク）
- 文字起こし: `HH:MM:SS` + Speaker N + 本文。クリックでその時刻へシーク
- 要約: 表題ブロック（日時・場所・講師）、**要約**、**知識ポイント**（階層）、**課題**（番号付き）
- 右レール: マインドマップ、目次（要約 / 知識ポイント / 課題）

Plaud のロゴ・コピーライト・「公式サイト」は載せない。面の構成と操作を揃える。

---

## 結論

会議（録音）1件につき `https://plaud.kitepon.dev/m/<id>` を1枚用意し、同じタブ構成にする。データはパイプラインが書いた JSON と MP3。GrokBot が要約構造を埋める。公開ホストは MS-A2 + Cloudflare Tunnel `home-server` + Access（自分のメールだけ）。R2 / Pages は使わない。メールは本線ではない。

---

## 画面

| パス | 中身 |
|---|---|
| `/` | 会議一覧（日時・長さ・タイトル）。Access 内 |
| `/m/<id>` | プレイヤー + タブ。`?tab=transcript` / `?tab=summary` |
| `/m/<id>/audio` | MP3（同一オリジン、プレイヤー用） |

要約タブの本文スキーマ（GrokBot が `notes` の代わりに JSON で書く）:

```json
{
  "title": "...",
  "started_at": "2026-08-18T13:00:25",
  "location": "",
  "people": [],
  "summary": "段落...",
  "knowledge": [{ "heading": "...", "items": [{ "title": "...", "body": "..." }] }],
  "issues": ["..."]
}
```

マインドマップは `knowledge` の木を SVG で描く。外部サービスは使わない。

文字起こしはセグメント配列:

```json
{ "t": 0, "speaker": "Speaker 1", "text": "..." }
```

現状の Whisper small は話者なし。v1 は時刻付き1話者でもページは出す。話者分離は次段（tdrz / 別モデル）。公式ページと同じ Speaker 列は、分離が載った会議から有効化する。

---

## データと公開

`plaud-inbox` に足す:

- `export <id>` … `data/meetings/<id>/meta.json` `transcript.json` `summary.json` `audio.mp3`
- `publish <id>` … R2 へオブジェクトを上げ、Pages が読む索引 `index.json` を更新

音声は git に入れない（5時間の MP3 がある）。R2 キーは会議 id。

GrokBot 手順の末尾に `export` → `publish` を足す。メールは残してよい。ページが本命の閲覧面になる。

---

## 実装の置き場

`Developer/plaude` 内:

```
web/          # 静的フロント（一覧・会議ページ）
scripts/plaud-inbox  # export / publish を追加
```

フロントは Vite + 素の TS。YuiHome の TanStack テンプレは使わない（別ホスト・別責務）。

デプロイ:

1. Cloudflare Pages: `plaud.kitepon.dev` → `web/` のビルド
2. R2 バケット `plaud-meetings`（audio + JSON）
3. Pages Functions か `_worker` で `/m/:id/audio` と JSON を R2 から出す
4. DNS: `plaud.kitepon.dev` CNAME → Pages。既存の `*.kitepon.dev` と同じ Cloudflare
5. Access: 自分の Gmail のみ（`afk.kitepon.dev` と同じ方針）

Access の設定と DNS は Cloudflare 側の操作。リポジトリ側は wrangler 設定まで用意する。ゾーン操作がこの環境からできないなら、CNAME と Access の中身だけ手順として残す。

---

## やらないこと

- Plaud 公式アセットの複製、Plaud へのリバースプロキシ
- YuiHome への混在
- 全世界に会議を公開する
- 初回から完全な話者分離（ページは先、分離は次）

---

## 受入

1. パイプライン済みの1会議（例: 6秒試験、または安全教育）が `/m/<id>` で開く
2. 文字起こしタブでプレイヤーが動き、タイムスタンプでシークできる
3. 要約タブに要約・知識ポイント・課題・目次がある
4. 一覧から会議に入れる
5. Access なしでは中身が見えない
6. `npm` ビルドが通る

---

## 作業順

1. `summary.json` / `transcript.json` の型と `export`
2. `web/` の2タブページ（モック1件で面を先に合わせる）
3. R2 publish + Pages 配線
4. GrokBot 用に SKILL.md を更新（要約 JSON の書き方 + publish）
5. `plaud.kitepon.dev` の DNS / Access
