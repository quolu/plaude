# Windowsの文字起こし接続

Whisper large-v3を継続し、FoxのWindows上へasr-workerを再構築した。
実行は要求時に自動起動し、標準OpenSSHの自動起動により再起動後も要求を受ける構成。
モデル・venv・設定はディスクへ保存し、ログイン中のセッションを前提にしない。

Plaudeはworkerのprepareから投函先・回収先を取得してscpする。
submitで起動し、statusがdoneになってからresult.v2を回収する。
WindowsのPowerShell構文とパスを利用者へ持たせない。

| 確認 | 結果 |
|---|---|
| 実録音10分 | coverage 1.0、93セグメント、3話者、反復0、未割当0 |
| 実録音約95分 | 投函から回収415.368秒、coverage 1.0、1,232セグメント、8話者・547 turn、反復0、未割当0.16% |
| SSH切断後の処理継続 | 確認済み |
| SSHでの日本語エラー回収 | UTF-8で一致 |
| 接続不能・失敗・v1結果・未知statusの保留 | focused testで確認 |
| Fox本体の再起動後 | 再起動の了承待ち |
| GrokBotの定期処理 | 実行環境の確認待ち |
| GitHubへの通常push | 本体とPlaudeのmainへ反映済み |
| 公開コミット導入後の確認 | 10分の実録音を再投函し、93セグメント・3話者・coverage 1.0・反復0で回収 |

確認結果は既存ASR比較画面の「WindowsのSSH投函経路」に掲載した。
録音と転写はprivateな一時ディレクトリだけへ保存し、既存会議の公開データは変更していない。

## 続き

Foxの再起動が許可されたら、実行中の確認ジョブが無いことを確かめて再起動し、
SSH復旧後に別IDの10分音声をPlaudeから投函する。手動ログインやアプリ起動は行わない。
本体の公開コミット76da883をFoxへinstall.ps1で導入し直した。導入済みファイルのSHA-256は公開コミットと一致し、origin/mainの祖先であることも確認した。
GrokBotの実行環境が判明したら、公開手順でリポジトリを更新し、個人configのasr_hostをFoxへ更新して疎通を確認する。

asr-worker本体の実装・導入手順は[本体README](../../asr-worker/README.md)と[復旧記録](../../asr-worker/docs/windows-native-20260928.md)を参照する。
