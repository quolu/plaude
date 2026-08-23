# plaud.kitepon.dev — 会議ごとの文字起こし／要約ページ

**R2 / Cloudflare Pages / メール本線は撤回済み。** 現行の正本は [AGENTS.md](../AGENTS.md) と [deploy/README.md](../deploy/README.md)。本書のホスト案は残すが、それに従わない。

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
| `/m/<id>` | プレイヤー + 文字起こし / 要約。タイトル下からダウンロード |
| `/m/<id>?p=<n>` | フェーズ n へ直リンク（音声も該当時刻へ移動する） |
| `/templates` | テンプレ一覧・作成・編集 |
| `/m/<id>/audio` | MP3（同一オリジン、プレイヤー用。Range / 206） |
| `/m/<id>/transcript.txt` | 文字起こしの平文（話者交代に `[MM:SS Speaker N]`）。添付名 `{id}-transcript.txt` |
| `/m/<id>/summary.md` | 要約 Markdown。添付名 `{id}-summary.md` |

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

`plaud-inbox publish <id>` は `site_origin` の `/api/publish` へ会議の meta / transcript / summary を送る。origin は次の形で保存する。

```
DATA_DIR/
  meetings/<id>/meta.json
  meetings/<id>/transcript.json
  meetings/<id>/summary.md または summary.json
  meetings/<id>/audio.mp3
```

音声は大きな POST にせず、MS-A2 の origin が Plaud から pull する。録音本文と本番音声は git に入れない。GrokBot の手順は render の次に publish を実行し、publish 成功時だけ completed とする。メールは本線から外し、既定 `steps.mail=false` の任意機能にする。

---

## 実装の置き場

`Developer/plaude` 内:

```
web/                  # Vite + 素の TS の一覧・会議ページ
web-server/           # API と静的配信を担う origin
scripts/plaud-inbox   # pull / transcribe / render / publish
```

フロントは Vite + 素の TS。YuiHome の TanStack テンプレは使わない（別ホスト・別責務）。

デプロイ経路は Cloudflare Access → Tunnel `home-server` → Caddy → MS-A2 の Docker origin (`plaud-web`, LAN `192.168.1.2:18880`) とする。公開 URL は `https://plaud.kitepon.dev` だけで、Access は `kitepon@gmail.com` のみを通す。Cloudflare Pages と R2 は使わない。

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

1. `summary.json` / `transcript.json` の型とモック会議データ
2. `web/` の2タブページ（モック1件で面を先に合わせる）
3. `plaud-inbox publish` で origin API へメタデータ・文字起こし・要約を載せる
4. GrokBot 用に SKILL.md を更新し、メールを本線から外す
5. MS-A2 origin と Tunnel / Caddy / Access を配線する
