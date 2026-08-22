# plaud-pipeline

Plaud NotePin S の録音を、Plaud の文字起こし分数を使わずに取り込む。

手足は `plaud-inbox`。種類推定とテンプレ選択は GrokBot（または同等のエージェント）が行う。

正本の手順は [SKILL.md](SKILL.md)。

## 必要なもの

- macOS
- 公式 Plaud CLI ログイン（`npx @plaud-ai/cli login`、トークンは `~/.plaud/tokens.json`）
- `whisper-cli`（Homebrew の `whisper-cpp`）と GGML モデル
- `ffmpeg`
- 送信に Mail.app

```sh
brew install whisper-cpp ffmpeg
mkdir -p ~/.local/share/whisper
curl -L -o ~/.local/share/whisper/ggml-small.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin
npx --yes @plaud-ai/cli@0.3.11 login
```

## 入れ方

```sh
git clone https://github.com/quolu/plaud-pipeline.git
chmod +x plaud-pipeline/scripts/plaud-inbox
ln -sfn "$(pwd)/plaud-pipeline/scripts/plaud-inbox" ~/.local/bin/plaud-inbox
cp plaud-pipeline/config.example.json ~/.config/plaud-pipeline/config.json
# email_to を自分の宛先に直す
```

Grok / Claude から skill として読むなら:

```sh
ln -sfn "$(pwd)/plaud-pipeline" ~/.grok/skills/plaud-pipeline
```

## GrokBot に渡す文

1時間おきのジョブに、次をそのまま載せる。

```
https://github.com/quolu/plaud-pipeline の SKILL.md に従え。

1時間おきに、この Mac で plaud-inbox を使う。
手順は SKILL.md の「1時間おき」どおり。

- 認証は既に plaud login 済みの ~/.plaud/tokens.json を使う
- Plaud のクラウド文字起こしは使わない
- 宛先は ~/.config/plaud-pipeline/config.json の email_to
- 失敗した id は done しない
```

コマンドの実体:

`~/.grok/skills/plaud-pipeline/scripts/plaud-inbox`

または `PATH` が通っていれば `plaud-inbox`。

## 入れないもの

録音データ、文字起こし本文、`~/.plaud/tokens.json`、個人の `config.json` はリポジトリに置かない。
