# plaude-web のイメージと退避を残す量

MS-A2 の Docker イメージと、QNAP に置いた退避を、必要な分だけ残す。ホストの `~/plaude` は git checkout ではない。このスクリプトはリポジトリからホストへコピーして、ホスト上で実行する。コンテナの中では動かさない。

公開やコンテナの停止はしない。`docker system prune`、`docker image prune`、`docker builder prune`、`docker image rm --force` は使わない。他製品のイメージは消さない。

## 順番

1. **tag** — いま動いているイメージに `plaude-web:pre-<id>-<YYYYMMDD>` を付ける。`<id>` は英数字・`.`・`_`・`-`（例: イメージ ID の先頭 12 文字）。日付は UTC の `YYYYMMDD`。
2. **deploy** — Mac で `web/` をビルドし、[deploy/README.md](../../deploy/README.md) のとおり `~/plaude` へコピーして `docker compose up -d --build` する。`~/plaude/data` は送らない。
3. **health** — `curl -fsS http://127.0.0.1:18880/healthz` が成功するまで、次へ進まない。
4. **backup** — `plaude-image-retention backup --apply`
5. **retention** — `plaude-image-retention --apply`

health が失敗したときは 4 と 5 を走らせない。戻しは、手順 1 で付けた `pre-*` タグから行う。

## 何を残すか

イメージの対象は次の二つだけ。

- リポジトリ `plaude-web` のイメージ
- タグが外れていて、ラベル `com.docker.compose.project=plaude` が付いているイメージ

残すのは次。

- `docker ps -a --filter ancestor=<id>` に出るイメージ（止まっているコンテナも含む）
- いちばん新しい `pre-<id>-<YYYYMMDD>` タグのイメージ。同じ日付が複数あるときは、イメージの作成時刻が新しい方

それ以外は、イメージ ID を一つずつ `docker image rm <id>` で外す。`-f` は付けない。失敗した ID は残し、他の ID へ進む。コンテナが使い始めた ID は、その場で外すのをやめる。

`plaude-web` 以外のタグが同じ ID に付いているイメージは消さない。その ID を消すと、他製品のタグも消える。そのタグは「いちばん新しい pre」にもしない。

QNAP の退避セットは、`/var/mnt/qnap-backups/main-server/products/plaude/<pre-id>/<YYYYMMDD>/` である。中身は `plaude-web.tar`、`plaude-web.tar.sha256`、`source/Dockerfile`。検証済みとは、その場で `sha256sum -c plaude-web.tar.sha256` が成功すること。Dockerfile が無くても、tar と sha256 が一致すれば検証済みとして扱う。

検証済みセットは、新しい方から数えて **3 個** または **500MiB（524288000 バイト）** の、先に上限へ当たる方まで残す。いちばん新しい検証済みセットは、それ一つで 500MiB を超えていても消さない。未完了（`.partial` / `.replacing`）、sha256 が一致しないもの、tar か sha256 が無いものは残さない。読めないセットは消さず、コマンドを失敗させる。

例:

- 検証済みが 4 個で、新しい 3 個の合計が 500MiB 以下なら、3 個残して最も古い 1 個を消す
- 新しい方から足して 500MiB を超えるなら、超える手前まで（いちばん新しい検証済みは残す）
- 検証済みが 1 個で 800MiB なら、その 1 個は残す

ローカルの tar は `~/plaude-image-backups`（`~/plaude/data` でも QNAP の上でもない）。完成した `*.tar` は最大 1 つ。`backup` が QNAP 側の sha256 を確認したあとは、ローカル tar を消す。確認に失敗したときは、その tar を 1 つ残す。

## ディスクの読み方

ローカルディスク（KIOXIA）の大きい読みは `ionice -c3` かつ 10MiB/s 以下。

- `docker save` は `ionice -c3` のあと、出力を 1MiB ごとに 0.1 秒空けて受ける。読み自体は dockerd が行うので、速度の上限はクライアント側の滞りで掛ける
- ローカル tar の sha256 は `ionice -c3 dd` で読み、同じ上限で流す
- QNAP へのコピーは `ionice -c3 rsync --bwlimit=10m`。`10m` は 10MiB/s で、rsync 3.2.3 以降の接尾辞である

## コマンド

初回と、スクリプトを更新したときはホストへ置く。

```bash
ssh kite@192.168.1.2 'mkdir -p ~/plaude/scripts/ops'
scp scripts/ops/plaude-image-retention kite@192.168.1.2:~/plaude/scripts/ops/plaude-image-retention
ssh kite@192.168.1.2 'chmod +x ~/plaude/scripts/ops/plaude-image-retention'
```

`~/plaude/scripts` はホスト側の手順用であり、イメージには焼かない。`data/` の中には置かない。

計画だけ見る（既定。ファイルもイメージも変えない）:

```bash
ssh kite@192.168.1.2 '~/plaude/scripts/ops/plaude-image-retention'
ssh kite@192.168.1.2 '~/plaude/scripts/ops/plaude-image-retention backup'
```

QNAP のパスが NFS でないマシンでは、空のディレクトリを「退避が無い」と見なさないよう、ここで止まる。

本番の一連:

```bash
short=$(ssh kite@192.168.1.2 'docker image inspect --format "{{.Id}}" plaude-web:latest')
short=${short#sha256:}
short=${short:0:12}
day=$(date -u +%Y%m%d)
ssh kite@192.168.1.2 "docker tag plaude-web:latest plaude-web:pre-${short}-${day}"

# deploy/README.md の rsync と docker compose up -d --build

ssh kite@192.168.1.2 'curl -fsS http://127.0.0.1:18880/healthz'
ssh kite@192.168.1.2 '~/plaude/scripts/ops/plaude-image-retention backup --apply'
ssh kite@192.168.1.2 '~/plaude/scripts/ops/plaude-image-retention --apply'
```

`backup --apply` は、いちばん新しい `pre-*` を `docker save` し、sha256 を書き、上の rsync で QNAP の `<pre-id>/<YYYYMMDD>/` へ tar、sha256、`~/plaude/Dockerfile` を置く。QNAP 側で `sha256sum -c` が成功してから、ディレクトリ名を確定し、ローカル tar を消す。イメージは消さない。古い QNAP セットも、このコマンドでは消さない。

`--apply` のない実行が計画、`--apply` が実行である。両方を同時には渡さない。

出力には、残したイメージと消したイメージ、QNAP セット、ローカル tar、`bytes_freed` が出る。イメージの `bytes_freed` は消したイメージの `Size` の合計である。残したイメージと層を共有している分はディスクに残る。QNAP のバイト数は消したファイルの合計である。

## 戻し

health 失敗の直後で、まだ retention を走らせていなければ、ローカルに `pre-*` が残っている。

```bash
ssh kite@192.168.1.2 'docker tag plaude-web:pre-<id>-<YYYYMMDD> plaude-web:latest'
ssh kite@192.168.1.2 'cd ~/plaude && docker compose up -d --no-build --pull never --force-recreate'
ssh kite@192.168.1.2 'curl -fsS http://127.0.0.1:18880/healthz'
```

ローカルのイメージが無いときは、いちばん新しい検証済みセットから戻す。`docker load` はコンテナを止めない。タグを付け替えて compose を上げる段で、origin は一度止まる。

```bash
ssh kite@192.168.1.2 'docker load -i /var/mnt/qnap-backups/main-server/products/plaude/<pre-id>/<YYYYMMDD>/plaude-web.tar'
```

load のあと、上の tag と `compose up --no-build` を行う。`~/plaude/data` は触らない。
