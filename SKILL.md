---
name: plaud-pipeline
description: Plaud NotePin S の録音を公式CLI/APIで音声取得し、LAN内 asr-worker で文字起こし、テンプレで資料化して plaud.kitepon.dev に載せる。GrokBotの1時間おきチェック、議事録、テンプレート選択、NotePin 取り込みに使う。Use when the user runs /plaud-pipeline.
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
2. 各件: `plaud-inbox pull <id>` → `plaud-inbox transcribe <id>`（SSH で asr-worker の投函箱へ音声を渡し、`result.json` を回収する）
3. `plaud-inbox outline <id>` の `outline` から文章の種類を推定する
4. `plaud-inbox templates --json` の `when` と照合し、テンプレ `id` を1つ選ぶ。同じ JSON の `sections` が、そのテンプレで**書かなければならない節**と各節の記入指示。テンプレは Plaud 公式（web.plaud.ai のテンプレコミュニティ）由来の16種
5. `plaud-inbox phases --id <id> --json '[{"t": 0, "title": "開会挨拶"}, ...]'`（会議をフェーズへ分ける。`t` は元音声の絶対秒で、`result.json` の `segments` の時刻から取る）
6. 要約を書く前の検品（2026-08-23 追加。GrokBot 初回実走の採点で確立）
   - **固有名詞**: 文字起こし中の社名・路線名・装置名に誤変換の疑いがあれば、要約へ写す前に `vocab add` で登録し、要約には正表記だけを書く
   - **人名の漢字**: 音声からは読みしか確定しない。表記を確認できない人名は役職＋姓（例: 斉藤部長）に留め、漢字のフルネームを推定して書かない
   - **重大事実**: 死亡・重傷・列車衝突などの重大災害は要約から絶対に落とさない。圧縮しても死傷の有無と結果は残す
7. `plaud-inbox summarize --id <id> --template <template_id> --json '{"節名": "本文", ...}'`（節をすべて埋める。1つでも欠けると失敗する）
8. `plaud-inbox publish <id>`（`site_origin` の `/api/publish` へ meta / transcript / summary を送る。音声は MS-A2 が Plaud から pull）。載った会議は `https://plaud.kitepon.dev/m/<id>` から文字起こし平文と要約 Markdown をダウンロードできる
9. `mail` は呼ばない。送れない・起こし失敗は `done` せず次週に残す。デモ音（シリアルが `882` 以外）は `list-new` に出ない。publish が成功した時だけ completed になる

端末録音だけを対象にする。すでに `completed` の id は触らない。

## コマンド

| コマンド | 役割 |
|---|---|
| `list-new --json` | 未完了の端末録音 |
| `pull [id...]` | MP3 取得 |
| `transcribe [id...]` | LAN 内 asr-worker へ SSH 投函し、完了まで status をポーリングして `result.json` を回収 |
| `outline <id>` | 分類用の先頭テキスト |
| `templates --json` | 選択可能なテンプレ |
| `phases --id --json` | フェーズ（章）分け。`[{"t": 秒, "title": "章名"}]` |
| `summarize --id --template --json` | テンプレの節ごとに本文を埋め、公開する要約を作る |
| `mail --id` | 明示的に有効化した場合だけ使う任意の残り |
| `publish <id>` | サイト API へ会議を載せる |
| `done <id>` | 完了印（publish 成功時は自動。失敗時は付けない） |
| `status --json` | 処理状態 |
| `prepare` | 未処理を pull+transcribe まで一括 |

id なしの `pull` / `transcribe` は未完了分を対象にする。

## 固有名詞の登録

転写で固有名詞（社名・部署名・人名）の誤変換に気づいたら、その場で asr-worker の登録簿へ登録する:

```
ssh fox-wsl "~/asr/bin/vocab add '正表記' '誤変換1,誤変換2'"
```

次回の転写から認識バイアスと置換補正の両方に効く。正表記は最短の正しい単位で登録する（長い複合語へ寄せると別の語を壊す）。

## テンプレの追加

Plaud 公式アプリのテンプレコミュニティで良いテンプレを見つけたら、サイトの `/templates` ページで新規作成し、本文をこの形式で貼る:

```
## 節の見出し
> この節に何を書くかの記入指示
```

`## 見出し` が summarize で埋めるべき節、直下の `>` がその記入指示になる。

## 制約

- 認証は `~/.plaud/tokens.json`（`npx @plaud-ai/cli login`）。切れたら login をやり直す
- 起こしは config のフラットな `asr_host` / `asr_engine` で指定する LAN 内 asr-worker の SSH 投函箱だけ。Plaud のクラウド文字起こし、ローカル Whisper の直叩き、テンプレ生成は呼ばない
- **フェーズと要約は publish の必須条件**。`phases` と `summarize` を済ませていない id は publish できない（失敗して done しない）
- フェーズは実際の話の切れ目で切る。長さを揃えるための機械的な等分割をしない。冒頭は 60 秒以内から始める
- 節に書くことが無ければ「なし」「未定」「明示なし」と書く。空文字は受け付けない
- メール宛先の既定は config の `email_to`。送信は sendmail / `mail` / SMTP（`PLAUD_SMTP_PASSWORD`）。Mail.app は Mac の残り
- トークン・個人 config・パスワードをリポジトリに書かない
