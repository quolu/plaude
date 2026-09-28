# ローカルASR比較の実測と現在地

現時点ではMOSS・Buzzへの置き換えを見送る。正解付き音声32件の予備比較で既存設定のWhisperを上回る改善を確認できず、MOSSには全長の資源・話者ID統合、Buzzには文字破損の課題が残る。Cohereはモデル取得条件への同意待ちで未計測のため、3候補全部の比較は未完了。

Windows nativeのCUDA推論はMOSS・Buzz・Whisperで成立した。本番設定、SSH投函箱、公開済み会議は変更していない。

## 目的と条件

Cohere Transcribe 2B、MOSS-Transcribe-Diarize 0.9B、BuzzASR Japaneseを、FoxのWindowsとRTX 5090で比較する。既存Whisper large-v3を基準に、文字起こしの品質向上を確認する。本番設定と公開済み会議の文字起こしは変更しない。

実会議は8月の比較と同一の5,683.160秒の録音。SHA-256は`24e23ecaeabbfc2ad471f826854f02bd7825a3a21f83684b0f7fda24073d6352`。録音と転写本文はGit管理せず、一時ディレクトリだけに保存する。音声はLANから出さない。公式配布のモデルを取得してからオフライン推論する。

前回の全文に対する人手の正解データは見つかっていない。公開正解音声FLEURSの日本語test先頭32件を固定した予備比較で文字誤り率を測り、実会議では10分、旧崩壊区間、全長の順に完走・欠落・反復・固有名詞・時刻・話者を確認する。公開音声の予備比較だけで採用を決めない。公開音声32件の合計は389.40秒、最長18.60秒で、Buzzの30秒入力枠による切り捨てはない。CohereとBuzzASRが出さない時刻・話者は未対応と表示する。

## 再開に必要な情報

- 比較スクリプト: `scripts/compare-local-asr.py`
- Foxの一時作業ディレクトリ: `C:\Users\kite_\AppData\Local\Temp\plaude-asr-comparison-20260928`
- 永続SSH端末: Aiterm `plaude-asr-comparison`
- Python 3.12.14 / PyTorch 2.11.0+cu128 / Transformers 5.17.0 / CTranslate2 4.8.2 / faster-whisper 1.2.1を比較専用venvへ導入済み。MOSS公式補助パッケージはcommit `61bc29cd4120be7b5d3b761b64cd5dff57263642`。
- モデルrevisionはスクリプトで固定する。実効環境・時間・GPUメモリ・各出力をJSONへ保存する。
- Cohere取得はHugging Faceが403を返した。Foxの認証アカウントでモデルカードの取得条件への同意が必要。ユーザーへ依頼済み。代替配布元や別モデルへ切り替えない。
- Hugging Faceの認証アカウントは`QuoLu`。Cohereの比較だけ、このアカウントでの取得条件への同意が必要。
- MOSS、BuzzASR、Whisperのモデル取得と素材準備は完了。3種類ともWindowsでCUDA推論に成功した。Foxで先に動いていたアプリは停止せず、推論前のGPU使用量は約8.5GBだった。
- MOSSの全長比較は完了（1,980.91秒・約33分）。Buzzの全長比較も完了（267.58秒・約4分28秒）。Whisperは既存実装と生成設定を揃えた測り直しを全て完了（全長299.20秒・約4分59秒）。MOSSは20分入力でCUDA確保量が38.7GiBに達したため、全長では発話間で10分以内へ区切り30秒を重ねる。重複の全出力を保存し、セグメント中央の時刻で所属を決める。話者IDは各入力内だけで有効と表示し、全録音の話者再識別を成功扱いしない。
- 公式Windows版PyTorchの`torch.backends.cuda.is_flash_attention_available()`は`False`だった。このAPIの値だけで実際に選択されたSDPAの全バックエンドは確定しない。2.11は公式MOSS手順のCUDA 12.8配布から得た版で、PyTorch全体の最新版を意味しない。
- 結果JSONのMac回収先は一時ディレクトリ`/var/folders/v4/ntdd_q2d10q962kq3cfx8lr00000gn/T/plaude-asr-20260928-upb6z6b2`。
- 比較画面は`http://127.0.0.1:18881`。Aiterm `plaude-asr-results`で`scripts/asr-comparison-report.py`を起動している。待受はMacのloopbackだけ。結果のJSONと会議音声はGitへ入れない。

## 予備比較の実測

全モデルとも語彙ヒント・文字列置換は使っていない。既存公開会議のWhisper転写には社名補正が入っているため、本比較の未補正出力と同じ得点として扱わない。

| モデル | FLEURS先頭32件の文字誤り率 | 32件の処理時間 | 会議冒頭10分 | 旧崩壊区間20分 | 全長95分 |
|---|---:|---:|---:|---:|---:|
| Whisper large-v3 | 5.04% | 18.97秒 | 22.50秒 | 63.67秒 | 299.20秒 |
| MOSS 0.9B | 18.29% | 49.84秒 | 74.93秒 | 375.29秒 | 1,980.91秒 |
| BuzzASR Japanese | 8.08% | 19.15秒 | 23.71秒 | 65.51秒 | 267.58秒 |
| Cohere Transcribe | 未実施 | 同意待ち | 同意待ち | 同意待ち | 同意待ち |

表の時間はASR推論と出力保存の壁時計時間で、モデルの読み込みと事前の音声処理は含まない。WhisperはASRのみ、MOSSはモデル内の時刻・話者出力を含む。外付け話者分離・強制アラインメント・要約・公開の時間は含まない。

文字誤り率は正解文1,547文字に対して、NFKC・小文字化・句読点/記号/空白の除去を全モデルへ共通適用した文字単位の編集距離。漢数字とアラビア数字等の表記差は残す。先頭32件を固定した予備比較であり、FLEURS全650件や実会議全体の精度を示さない。

MOSSは旧崩壊区間で「日本電設工業」を2回正しく出し、山崎部長の挨拶を出力した。Buzzの同区間には置換文字`U+FFFD`が43個含まれる。これらは生成出力JSON内で確認したもので、端末ログの文字化けとは区別する。元の12語の採点リストと4つのForcedAligner anchorは未復元なので、元の完全一致率と時刻誤差は同条件の数値として再計算していない。

Buzzの初回FLEURS実行は比較スクリプトの出力上限がWhisperの開始トークンを含む448位置を1トークン超えて停止した。上限を447へ直し、公式例のfloat16・反復制御設定で再測定した。会議入力は短い休止の前後を28秒枠内へまとめ、文脈を保つ。`no_repeat_ngram_size=0` / `repetition_penalty=1.0`へ変えた対照実験も完了した。公式設定の結果は上書きしない。

## Whisper基準の測り直し

最初のWhisper基準は`condition_on_previous_text=True`と既定の生成設定で測定していた。既存`asr-worker/asr_worker/engines/whisper.py`はFalse・`no_repeat_ngram_size=4`・`repetition_penalty=1.1`・`word_timestamps=True`・`hallucination_silence_threshold=2.0`・温度列`[0, .2, .4, .6, .8, 1]`である。最初の数値は比較から除外し、一時ディレクトリの`wrong-whisper-settings-pilot/`へ退避した。正式な基準は既存実装と同じ設定で、語彙ヒントなしで測り直す。前処理のhighpass 60Hz・loudnormも既存runnerと一致している。

正式Whisperの20分出力にもU+FFFDが4個含まれた。Buzzだけの問題とは断定せず、同じ指標で記録する。

## 全長の観測

MOSSは11入力の全てを完走し、28,979文字・896セグメントを出力した。末尾の発話endは5,586.77秒、入力長を超えたセグメント0、入力内のstart逆転0、U+FFFDは0。VAD区間4,844.90秒に対する時刻区間の重なりは97.42%、未重複124.83秒。この値を単語の欠落率とは扱わない。

20分入力で2回出た社名の正表記は、10分以内へ分割した全長出力では0回だった。文字列の出現数による観測であり、固有名詞の完全な採点ではない。長い入力で得た一部の改善が短い入力でも維持されるとは確認できていない。全録音の話者ID統合も未実施。

Buzzは257入力の全てを完走し、27,310文字を出力した。U+FFFDは202個、社名の正表記0回。CUDA最大確保3.15GiB・予約3.46GiB。話者と文字の時刻は未対応。公式設定の全長処理は速いが、生成文字列が壊れる問題は解決していない。

正式Whisperの全長は26,772文字・1,232セグメント、末尾end 5,586.35秒、入力長超過0、start逆転0、U+FFFDは2個だった。VAD区間との重なりは88.80%だが、単語時刻から作る細かい区間とMOSSの区間は粒度が異なり、欠落率として比較しない。BuzzとWhisperの速度差は31.62秒で、話者分離・要約・公開はどちらも含まない。

## 反復制御を外した対照実験

`no_repeat_ngram_size=0` / `repetition_penalty=1.0`に変更し、その他の生成設定は各モデルのままにした。2つの設定を一緒に変える対照であり、どちら単独の寄与かまでは切り分けていない。

- Buzzの公開32音声は、6.96秒のID 1731で出力上限に達して失敗。トークンID 51866を447回生成し、特殊トークンを除いた本文は空だった。32件のCERは未算出とし、途中までの結果で得点化しない。
- Buzzの会議20分は60.01秒で完走。U+FFFDは43個から10個に減ったが、破損は残る。社名の正表記は0回。
- Whisperの公開32音声は18.58秒で完了し、CERは5.04%から4.33%へ下がった。全長でのこの設定の品質と反復は未確認なので、本番設定へ採用していない。
- Whisperの会議20分は67.42秒で完走。U+FFFDは4個から0個になった。ただし全長での制御なし設定の反復と品質は未検証で、本番へ反映していない。

## 資源と計測の限界

MOSS全長の7区間完了後、WindowsのGPU Process Memoryカウンタで当該Pythonプロセスの専用GPUメモリ25.28GiB・共有GPUメモリ7.90GiBを観測した。観測時刻は2026-09-28 04:20:13 UTC。瞬間値であり最大値ではない。最初の2入力は約70秒、3〜7入力は約173〜244秒かかっている。全長の最大CUDA確保は11.39GiB、最大予約は32.51GiBで、予約量が計算用の確保量より大きい。共有メモリ使用は確認できたが、予約量が増える内部原因と遅延への寄与は未解明であり、キャッシュ解放等で症状を隠す変更はしていない。

`scripts/asr_comparison_metrics.py`が出力文字数・U+FFFD・VAD区間と出力時刻の重なりを集計する。VADの重なりは単語の欠落率ではない。Whisperは単語時刻から作る区間、MOSSはモデルが直接生成する区間で粒度も異なるため、精度順位に使わない。CohereとBuzzの文字時刻は生成していないため未計測。WhisperのCTranslate2確保量はPyTorchの統計に入らず、GPUメモリ0として比較しない。

## 検証と変更範囲

比較スクリプトと集計・閲覧スクリプトのPython構文検証に成功。MOSS・Buzz・正式Whisperの公開32件、冒頭10分、20分区間、全長の推論は完了した。Buzzの反復制限なし・公開32件は生成上限で失敗し、その出力を成功結果として掲載していない。残りの対照実験は完了。

Chromeでグラフと数値、MOSSの入力別話者表示、生成失敗の表示、音声の2,000秒へのシークを確認し、JavaScriptエラーは0。比較画面の音声配信はRange/206に対応する。音声と転写本文はリポジトリ外だけに保存した。既存の別作業の差分には触れていない。通常pushは行わない。

## 再現とCohereの再開

録音の本文を含むファイルは下記の`$taskDir`へ置く。モデルの取得と素材準備は完了しているため、現在地からの再開時には繰り返さない。

```powershell
$taskDir = Join-Path $env:TEMP 'plaude-asr-comparison-20260928'
# CohereはQuoLuで取得条件へ同意した後だけ実行する。
& "$taskDir\venv\Scripts\python.exe" "$taskDir\compare.py" download --root $taskDir --engine cohere
# モデルの取得成功を確認してから、各推論を順番に実行する。
foreach ($suite in @('fleurs','10min','recovery','full')) {
    & "$taskDir\venv\Scripts\python.exe" "$taskDir\compare.py" run --root $taskDir --engine cohere --suite $suite
    if ($LASTEXITCODE -ne 0) { throw "Cohere $suite の比較失敗" }
}
```

BuzzとWhisperの対照実験は`run --engine buzz --suite fleurs --decoding plain`と`run --engine buzz --suite recovery --decoding plain`。結果は`buzz-plain-*.json`と`whisper-plain-*.json`へ別名で保存する。失敗は`*-failure.json`へ出力と生成トークンを残して非ゼロで終了する。依存パッケージの実効版は一時ディレクトリの`packages.txt`へ保存した。

## 出典

- [前回の実会議比較](../../asr-worker/docs/search/synthesis.md)
- [Cohere](https://huggingface.co/CohereLabs/cohere-transcribe-03-2026)
- [MOSS](https://huggingface.co/OpenMOSS-Team/MOSS-Transcribe-Diarize)
- [BuzzASR](https://huggingface.co/BuzzASR/japanese)
- [FLEURS](https://huggingface.co/datasets/google/fleurs)
