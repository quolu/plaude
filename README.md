# plaude

Plaud NotePin S の録音を、Plaud の文字起こし分数を使わずに取り込む。

手足は `plaud-inbox`。種類推定とテンプレ選択は GrokBot（または同等のエージェント）が行う。

正本の手順は [SKILL.md](SKILL.md)。ランタイムは Linux（Grok Bot 環境）を第一とする。Mac / Mail.app は任意の残り。

## 必要なもの

- Linux（Grok Bot 環境）。macOS でも動くが必須ではない
- 公式 Plaud CLI ログイン（`npx @plaud-ai/cli login`、トークンは `~/.plaud/tokens.json`）
- `whisper-cli`（whisper.cpp）と `~/.local/share/whisper/ggml-small.bin`
- `ffmpeg`
- 送信: システムの `sendmail` または `mail`/`mailx`。なければ個人 config の SMTP（パスワードは環境変数。リポジトリには置かない）

```sh
# モデルは OS 共通
mkdir -p ~/.local/share/whisper
curl -L -o ~/.local/share/whisper/ggml-small.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin
npx --yes @plaud-ai/cli@0.3.11 login
```

Linux（Debian / Ubuntu / Grok Bot）:

```sh
sudo apt-get install -y ffmpeg git cmake build-essential
git clone https://github.com/ggml-org/whisper.cpp.git
cd whisper.cpp
cmake -B build && cmake --build build -j --config Release
mkdir -p ~/.local/bin
ln -sfn "$(pwd)/build/bin/whisper-cli" ~/.local/bin/whisper-cli
# ~/.local/bin を PATH に入れる
```

macOS（任意）:

```sh
brew install whisper-cpp ffmpeg
```

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
- Plaud のクラウド文字起こしは使わない。起こしはローカル whisper-cli + ggml-small.bin
- 宛先は ~/.config/plaud-pipeline/config.json の email_to
- 失敗した id は done しない
- 端末録音（シリアル 882 始まり）だけを対象にする
```

コマンドの実体:

`~/.grok/skills/plaud-pipeline/scripts/plaud-inbox`

または `PATH` が通っていれば `plaud-inbox`。

## 入れないもの

録音データ、文字起こし本文、`~/.plaud/tokens.json`、個人の `config.json`、SMTP パスワードはリポジトリに置かない。
