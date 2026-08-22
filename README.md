# plaude

Plaud NotePin S の録音を、Plaud の文字起こし分数を使わずに取り込む。

手足は `plaud-inbox`。種類推定とテンプレ選択は GrokBot（または同等のエージェント）が行う。

正本の手順は [SKILL.md](SKILL.md)。ランタイムは Linux（Grok Bot 環境）を第一とする。Mac / Mail.app は任意の残り。

## 必要なもの

- Linux（Grok Bot 環境）。macOS でも動くが必須ではない
- 公式 Plaud CLI ログイン（`npx @plaud-ai/cli login`、トークンは `~/.plaud/tokens.json`）
- LAN 内 asr-worker（RTX 5090 / WSL2）への SSH 到達。ssh alias `fox-wsl` を用意する（下記）
- `ffmpeg`
- 送信: システムの `sendmail` または `mail`/`mailx`。なければ個人 config の SMTP（パスワードは環境変数。リポジトリには置かない）

```sh
npx --yes @plaud-ai/cli@0.3.11 login
```

Linux（Debian / Ubuntu / Grok Bot）:

```sh
sudo apt-get install -y ffmpeg git
mkdir -p ~/.local/bin
# ~/.local/bin を PATH に入れる
```

文字起こしは**このマシンでは行わない**。LAN 内 asr-worker（`ssh fox-wsl`）へ SSH で投函し、
`result.json` を回収する。ローカル whisper を持たないのは設計であり、欠品ではない。

### asr-worker への ssh alias（2026-08-23 確立）

Grok Bot 環境（クラウド）からは、メインサーバを踏み台にして WSL2 へ直結する。
契約と運用条件の正本は [asr-worker](https://github.com/kitepon/asr-worker) の AGENTS.md。

```
Host fox-wsl
  HostName 192.168.1.11
  Port 2222
  User kite
  ProxyJump grokbot.kitepon.dev
  IdentityFile ~/.ssh/<grokbot.kitepon.dev に使っている鍵>
```

疎通確認は `ssh fox-wsl 'hostname && ls ~/asr/bin/submit'`（`FOX` が返れば開通）。

送信は `email_to` 宛。`mail_backend` が `auto` のとき、sendmail → `mail`/`mailx` → `smtp_host` →（Mac だけ）Mail.app の順。SMTP を使うなら個人の `config.json` に `smtp_host` / `smtp_port` / `smtp_user` を書き、パスワードは `PLAUD_SMTP_PASSWORD`。

## 入れ方

```sh
git clone https://github.com/quolu/plaude.git
chmod +x plaude/scripts/plaud-inbox
ln -sfn "$(pwd)/plaude/scripts/plaud-inbox" ~/.local/bin/plaud-inbox
mkdir -p ~/.config/plaud-pipeline
cp plaude/config.example.json ~/.config/plaud-pipeline/config.json
# email_to を自分の宛先に直す
```

Grok / Claude から skill として読むなら:

```sh
ln -sfn "$(pwd)/plaude" ~/.grok/skills/plaud-pipeline
```

## GrokBot に渡す文

1時間おきのジョブに、次をそのまま載せる。ジョブは Grok Bot 環境で回す。

```
https://github.com/quolu/plaude の SKILL.md に従え。

1時間おきに、Grok Bot 環境で plaud-inbox を使う。
手順は SKILL.md の「1時間おき」どおり。Mac や Mail.app は不要。

- 認証は既に plaud login 済みの ~/.plaud/tokens.json を使う
- Plaud のクラウド文字起こしは使わない。起こしは LAN 内 asr-worker（config の asr_host=fox-wsl、
  asr_engine=whisper）だけ。ローカル whisper の直叩きへフォールバックしない
- asr-worker へ届かない・status が返らない時は転写を保留する。別経路で代替しない
- 宛先は ~/.config/plaud-pipeline/config.json の email_to
- 失敗した id は done しない
- 端末録音（シリアル 882 始まり）だけを対象にする
```

コマンドの実体:

`~/.grok/skills/plaud-pipeline/scripts/plaud-inbox`

または `PATH` が通っていれば `plaud-inbox`。

## 入れないもの

録音データ、文字起こし本文、`~/.plaud/tokens.json`、個人の `config.json`、SMTP パスワードはリポジトリに置かない。
