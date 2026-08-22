---
name: plaud-pipeline
description: Plaud NotePin S の録音を公式CLI/APIで音声取得し、ローカルWhisperで文字起こし、テンプレで資料化して plaud.kitepon.dev に載せる。GrokBotの1時間おきチェック、議事録、テンプレート選択、NotePin 取り込みに使う。Use when the user runs /plaud-pipeline.
---

# Plaud pipeline

手足は `plaud-inbox`。種類推定とテンプレ選択はこのエージェントが行う。Plaud の文字起こし分数は使わない。ランタイムは Grok Bot 環境（Linux）。Mac / Mail.app は不要。

```
plaud-inbox = ~/.grok/skills/plaud-pipeline/scripts/plaud-inbox
config      = ~/.config/plaud-pipeline/config.json
```

設定変更は `plaud-inbox config` と `plaud-inbox config <key> <value>`。`steps.download` / `steps.transcribe` / `steps.mail` で各段を止められる。メールは任意の残りで、既定の `steps.mail=false` のまま有効化しない。

## 1時間おき（GrokBot）

Grok Bot 環境で回す。Mac は使わない。

1. `plaud-inbox list-new --json`
2. 各件: `plaud-inbox pull <id>` → `plaud-inbox transcribe <id>`
3. `plaud-inbox outline <id>` の `outline` から文章の種類を推定する
4. `plaud-inbox templates --json` の `when` と照合し、テンプレ `id` を1つ選ぶ
5. 資料本文（概要・決定・宿題など）を書き、`plaud-inbox notes <id> --text '...'` に渡す
6. `plaud-inbox render --id <id> --template <template_id>`
7. `plaud-inbox publish <id>`（`site_origin` の `/api/publish` へ meta / transcript / summary を送る。音声は MS-A2 が Plaud から pull）
8. `mail` は呼ばない。送れない・起こし失敗は `done` せず次週に残す。デモ音（シリアルが `882` 以外）は `list-new` に出ない。publish が成功した時だけ completed になる

端末録音だけを対象にする。すでに `completed` の id は触らない。

## コマンド

| コマンド | 役割 |
|---|---|
| `list-new --json` | 未完了の端末録音 |
| `pull [id...]` | MP3 取得 |
| `transcribe [id...]` | ローカル Whisper（10分チャンク） |
| `outline <id>` | 分類用の先頭テキスト |
| `templates --json` | 選択可能なテンプレ |
| `notes <id> --text` | Bot が書いた資料本文 |
| `render --id --template` | テンプレ適用 |
| `mail --id` | 明示的に有効化した場合だけ使う任意の残り |
| `publish <id>` | サイト API へ会議を載せる |
| `done <id>` | 完了印（publish 成功時は自動。失敗時は付けない） |
| `status --json` | 処理状態 |
| `prepare` | 未処理を pull+transcribe まで一括 |

id なしの `pull` / `transcribe` は未完了分を対象にする。

## 制約

- 認証は `~/.plaud/tokens.json`（`npx @plaud-ai/cli login`）。切れたら login をやり直す
- 起こしは `whisper-cli` + `~/.local/share/whisper/ggml-small.bin`。Plaud のクラウド文字起こしとテンプレ生成は呼ばない
- メール宛先の既定は config の `email_to`。送信は sendmail / `mail` / SMTP（`PLAUD_SMTP_PASSWORD`）。Mail.app は Mac の残り
- トークン・個人 config・パスワードをリポジトリに書かない
