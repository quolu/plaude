# AGENTS.md

plaude で働く全 AI 共通のプロジェクト規約。グローバル規約に加え、本書を優先する。

## 製品

Plaud NotePin S の端末録音を、Plaud のクラウド文字起こし分数を使わずに取り込み、Access 内の閲覧面へ載せる。

- 公開 URL は `https://plaud.kitepon.dev` だけ
- 作業場所は本リポジトリ（`/Users/kite/Developer/plaude`）だけ。YuiHome には書かない
- GitHub は `quolu/plaude`

取り込み手順の正本は [SKILL.md](SKILL.md)。origin の出し方は [deploy/README.md](deploy/README.md)。[docs/plan.md](docs/plan.md) の R2 / Cloudflare Pages / メール本線は撤回済みで従わない。

## 面

公式 Plaud Web の構成と操作に揃える。Plaud のロゴ・コピーライト・公式サイトへの誘導は載せない。公式へのリバースプロキシもしない。

| パス | 中身 |
|---|---|
| `/` | 会議一覧 |
| `/m/<id>` | プレイヤー + 文字起こし（フェーズ見出しで章分け）/ 要約。タイトル下から文字起こしと要約をダウンロードできる |
| `/m/<id>?p=<n>` | フェーズ n へ直リンク（音声も該当時刻へ移動する） |
| `/templates` | テンプレ一覧・作成・編集 |
| `/m/<id>/audio` | 同一オリジンの MP3（Range / 206 でシーク可能） |
| `/m/<id>/transcript.txt` | 文字起こしの平文（話者交代に `[MM:SS Speaker N]`）。添付名 `{id}-transcript.txt` |
| `/m/<id>/summary.md` | 要約 Markdown。添付名 `{id}-summary.md` |

Access は `afk.kitepon.dev` と同じく `kitepon@gmail.com` だけ。Access なしで中身を出さない。全世界公開にしない。

文字起こしは `{ "t": 秒, "speaker": "Speaker N", "text": "..." }`。話者が変わった行にだけラベルを出す（1252 行に同じ名前を並べない）。章をまたぐ時は先頭で出し直す。

## ホスト

origin は MS-A2 の Docker（`plaude-web`、LAN `192.168.1.2:18880`）だけ。経路は Cloudflare Access → Tunnel `home-server` → Caddy → origin。R2 と Pages は使わない。

静的面は `web/`（Vite + 素の TS）。API と静的配信は `web-server/` の1本。YuiHome のフロント枠は使わない。

image は Mac で `web/` を build してから linux/amd64 で送り、MS-A2 上で重い build はしない。

## データ

`DATA_DIR`（コンテナは `/data`）:

```
meetings/<id>/{meta.json,transcript.json,summary.md|summary.json,phases.json,audio.mp3}
templates/<id>.md
```

スキル同梱の初期テンプレは repo の `templates/`。会議の本番音声は git に入れない。モック fixture の短い MP3 だけ同梱してよい。

テンプレの本文は Markdown。frontmatter に `id` / `title` / `when` / `category` / 出典。コミュニティから取るのは名前・カテゴリ・説明・プロンプトだけ。公式画像は使わない。repo 既存6件は残す。

## パイプライン

手足は `scripts/plaud-inbox`。種類推定とテンプレ選択はエージェントが行う。

- 受け取る result.json は **`asr-worker.result.v2` だけ**。v1 は拒否して転写エラーにする（黙って受けない）
- 平文 transcript（`transcripts/<id>.txt`）は話者交代の位置に `[MM:SS Speaker N]` を挟む。outline / phases / summarize を書く側が「誰がいつ話したか」を読めるようにするため
- **publish の音声 URL は毎回取り直す。** Plaud の presigned URL は期限切れになるため、state に貯めた URL を使い回さない
- 起こしは LAN 内 `asr-worker` の SSH 投函箱（`asr_host` / `asr_engine`）だけ。Plaud クラウドの文字起こし、ローカル Whisper の直叩き、テンプレ生成は呼ばない
- メールは本線ではない。既定は `steps.mail=false`
- `publish` は `site_origin` へ meta / transcript / summary / summary_struct / phases を載せる。音声は origin 側が Plaud から pull する
- **テンプレは要約の器であり、要約そのものを規定する**。コミュニティ原文は逐語。`## 見出し` がある骨組み型は、その下が出力の形。`##` が無い指示型は `本文` 1キーで、`templates --json` の `ask` にプロンプト全文を乗せる。`summarize` は全節が埋まっている時だけ成功し、その出力（`docs/<id>.md`）が publish する summary の正本になる。文字起こし本文をテンプレへ埋め込まない。週次・現場・安全・提出物が主なら `meeting-minutes` だけ（`meeting-notes` は短い打合せ・雑談メモだけ）。骨組み型は見本の入れ子を守り、指示型は議題別の決定・TODO・保留で書く。フラットな時系列ダンプは summarize しない
- **フェーズ（章）は成果物の一部**。`phases` が `[{"t": 絶対秒, "title": 章名}]` を検証（単調増加・音声長以内・冒頭 60 秒以内）して保存し、閲覧面は章目次・章ごとの折り返し・`?p=<n>` の直リンクを出す
- `phases` と `summarize` を済ませない限り `publish` は失敗する。握りつぶして公開しない
- 認証は `~/.plaud/tokens.json`。個人 config は `~/.config/plaud-pipeline/config.json`
- トークン・個人 config・パスワード・録音本文をリポジトリに書かない
- 端末録音（シリアル `882` 始まり）だけを対象にする。デモ音は `list-new` に出さない
- publish に失敗した id は `done` しない

## git

通常 push は既定にしない。force 系・履歴改変は目的・影響・戻し方を書いてからだけ。
