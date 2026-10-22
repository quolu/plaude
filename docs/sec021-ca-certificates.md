# SEC021 準備記録 — plaude-web の CA 束

2026-10-22。これは本番更新の GO ではない。MS-A2 への配備、origin の再起動、本番 SSH での変更はしていない。検証データは repo のモック `mock-safety` と公開の HTTPS 先だけである。

## 結論

plaude-web のベースは `python:3.12-alpine` で、OS は Alpine Linux である。選んだ修正版は Alpine の `ca-certificates` / `ca-certificates-bundle` **`20261020-r0`**。Dockerfile はこの版と、ベース image の manifest list ダイジェストを固定する。ビルドは、信頼ストアに emSign ECC Root CA - G3 または AAA Certificate Services の根（証明書 SHA-256 または SPKI SHA-256）があれば失敗する。

この環境で組んだイメージは起動し、外向き HTTPS とモックでの主要 API が通った。戻し手順は、本番の現行イメージではなく公開の修正前ベースから組んだ代理イメージで、退避（tag と `docker save`）と戻し（tag と `docker load`）を試した。

## ベースの確認

2026-10-22 に registry を引いた結果、次の 3 タグは同一の manifest list だった。

| タグ | manifest list |
|---|---|
| `python:3.12-alpine` | `sha256:92abd2ba1bdfb48b1e2ac224b582dd1558d0d4bb11c903b126b5bf9c448fd656` |
| `python:3.12-alpine3.24` | 同上 |
| `python:3.12.15-alpine3.24` | 同上 |

linux/amd64（MS-A2 と同じ）の image digest は `sha256:9b98a8d37794ca093ba8d5afe1ffac52f5a15168b9b4e67594d86c20e14fa681`。image config の作成時刻は 2026-10-21T23:04:22Z、`PYTHON_VERSION=3.12.15`。

引いたイメージの `/etc/os-release`:

```
NAME="Alpine Linux"
VERSION_ID=3.24.3
PRETTY_NAME="Alpine Linux v3.24"
```

apk リポジトリは `v3.24/main` と `v3.24/community`。Alpine 3.24 の `ca-certificates` と `ca-certificates-bundle` はどちらも `20261020-r0`（2026-10-20 ビルド）だけが掲載されていた。`r1` 以降は無かった。Debian/Ubuntu 系のパッケージは、このイメージには入っていない。

このダイジェストのベースには、すでに `ca-certificates-20261020-r0` と `ca-certificates-bundle-20261020-r0` が入っていた。監査が指摘した本番コンテナは、それより前に組まれたイメージである。浮動タグのまま再ビルドすると、将来のベースが戻ったときに同じ指摘が再発する。そのため FROM のダイジェストと apk の版を両方固定する。

## 照合した根

名前の部分一致ではなく、証明書 DER の SHA-256 と SubjectPublicKeyInfo の SHA-256 で照合した。SPKI の切り出しは、この束の 359 証明書（修正前 curl 束、修正後 Alpine 束、AAA 根、修正前 Alpine 束）で OpenSSL の出力と一致することを確認してから使った。

| 根 | 出所 | 証明書 SHA-256 | SPKI SHA-256 |
|---|---|---|---|
| `CN=emSign ECC Root CA - G3,O=eMudhra Technologies Limited,OU=emSign PKI,C=IN`（自己署名） | Mozilla 束 `https://curl.se/ca/cacert-2026-09-25.pem`。修正前 Alpine `ca-certificates-20260611-r0` にも同じバイト列があった | `86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b` | `8d417db2dd8bf5e3084d1e3f196d583849d81bdd4c00c70b9d39369e96b8c782` |
| `CN=AAA Certificate Services,O=Comodo CA Limited,L=Salford,ST=Greater Manchester,C=GB`（自己署名。`openssl verify` 成功） | `http://crt.comodoca.com/AAACertificateServices.crt` | `d7a7a0fb5d7e2731d771e9484ebcdef71d5f0c3e0a2948782bc83ee0ea699ef4` | `bd153ed7b0434f6886b17bce8bbe84ed340c7132d702a8f4fa318f756ecbd6f3` |

利用者の言う emSign AAA は、このインシデントで G3 と組にして外す AAA Certificate Services（Comodo AAA Services root）として照合した。件名に `emSign AAA` を含む証明書は、修正前の Alpine 束にも修正後の束にも無かった。

Alpine `20260611-r0` には G3 が入っていた。AAA Certificate Services はその修正前の束にも入っていなかった。`20261020-r0` は G3 を外し、AAA は入ったままにならない。curl の 2026-09-25 束と 2026-10-20 束の差分では、G3 に加えて `emSign Root CA - C1` と `emSign ECC Root CA - C3` も外れていた。`emSign Root CA - G1`（証明書 SHA-256 `40f6af0346a99aa1cd1d555a4e9cce62c7f9634603ee406615833dc8c8d00367`）は修正後の束に残る。今回の拒否対象は G3 と AAA である。

## Dockerfile

- `FROM python:3.12.15-alpine3.24@sha256:92abd2ba1bdfb48b1e2ac224b582dd1558d0d4bb11c903b126b5bf9c448fd656`
- `apk add` で `ca-certificates=20261020-r0` と `ca-certificates-bundle=20261020-r0`。`apk list -I` にその 2 行が無ければ失敗する
- `web-server/sec021_trust_check.py` が `/etc/ssl/certs/ca-certificates.crt`、`/etc/ssl/certs`、`/usr/share/ca-certificates` を歩き、上の 2 根の証明書 SHA-256 か SPKI SHA-256 があれば失敗する。束の本数が 100 未満でも失敗する
- レガシー builder（この環境の Docker 29.1.3。BuildKit なし）で組める。シェル heredoc には依存しない

修正前ベース `python@sha256:285a71327884a4d50efbea30104473b0fa43ecefa499458899670ca30dae76e5`（Alpine 3.24.1、`ca-certificates-20260611-r0`）に同じ検査を載せたビルドは、次で失敗した。

```
banned root emSign ECC Root CA - G3 fingerprint in /etc/ssl/certs/ca-certificates.crt
```

## 検証

この環境は linux/amd64。本番 MS-A2 も linux/amd64 だが、ここで組んだ image id は本番の image id にはならない。`web/dist` はこの環境の `npm run build` であり、Mac で組んで rsync する本番の dist とは別にしている。

組んだイメージ: `plaude-web:sec021` = `sha256:3151ecd0fcfa5a104d81ee21f9a0cda84039180df6c3f63615aa164ee87fa644`（2026-10-22T11:51:04Z）。

### (a) 根照合

イメージから取り出した `/etc/ssl/certs` と `/usr/share/ca-certificates` を、ホストの OpenSSL で証明書ごとに subject / issuer / 証明書 SHA-256 / SPKI SHA-256 へ展開した。

- 束 `ca-certificates.crt` は 118 証明書、ストア全体のユニーク指紋も 118
- G3 の証明書 SHA-256 も SPKI も無い
- AAA Certificate Services の証明書 SHA-256 も SPKI も無い
- 件名に `emsign` または `aaa certificate` を含むものは `emSign Root CA - G1` だけ（束、`emSign_Root_CA_-_G1.crt`、ハッシュ名 `2923b3f9.0`、`ca-cert-emSign_Root_CA_-_G1.pem` は同じ証明書）
- イメージ内の再実行: `python /app/web-server/sec021_trust_check.py` → `sec021 ca bundle 118 unique 118`
- インストール版: `ca-certificates-20261020-r0`、`ca-certificates-bundle-20261020-r0`
- `/etc/ssl/cert.pem` は `certs/ca-certificates.crt` へのシンボリックリンク。Python の既定検証先 `cafile` は `/etc/ssl/cert.pem`

否定試験: `web-server/test_sec021_trust_check.py` が、同梱した公開の G3 PEM と AAA PEM を束に入れると検査が拒否することを確認した。

### (b) 外向き HTTPS

イメージの Python（既定の SSL コンテキスト。追加の CA ファイルは指定していない）で次が HTTP 200 だった。

- `https://example.com/`（HTML）
- `https://dl-cdn.alpinelinux.org/alpine/v3.24/main/x86_64/APKINDEX.tar.gz`（gzip）

Plaud の presigned URL への pull はしていない。publish の音声取得は同じ Python の既定検証を使うが、本番の URL では試していない。

### (c) 製品の通常動作

既存テスト（すべて終了コード 0）:

- `python3 web-server/test_server.py`（healthz、会議、音声の 206、文字起こし、要約、テンプレ、publish）
- `python3 scripts/test_plaud_inbox_publish.py`
- `python3 scripts/test_plaud_inbox_templates.py`
- `python3 scripts/test_plaud_inbox_worker.py`（5 件）
- `node web/test-seek.mjs`
- `node web/test-create.mjs`
- `python3 web-server/test_sec021_trust_check.py`

サイトは後述のローカル compose で `127.0.0.1:18880` に起動し、ボリュームは repo の `data/`（モック）である。`/healthz`、`/api/meetings`（`mock-safety` の 1 件）、`/api/meetings/mock-safety`、`/api/templates`（16 件）、`/`、`/m/mock-safety/transcript.txt`、`/m/mock-safety/summary.md`、`/m/mock-safety/audio` の Range `206` を確認した。確認後に `docker compose down` した。

### (d) 更新後イメージの起動

`plaude-web:sec021` を `plaude-web:latest` に tag し、`docker compose up -d --no-build --pull never --force-recreate` した。起動したコンテナの image id は `sha256:3151ecd0fcfa5a104d81ee21f9a0cda84039180df6c3f63615aa164ee87fa644`。`/healthz` は `ok`。束に G3 も AAA も無かった。

### (e) 旧イメージへ戻す

本番の `plaude-web` はレジストリに無いので、ここからは取れない。戻しの動作確認には、修正前の公開ベースから組んだ代理イメージを使った。

- 代理の旧イメージ: `plaude-web:sec021-rehearsal-before` = `sha256:805d26586e7e03a2d8bba45ab4d726056151a941044b9bb5d55ad96165065b53`
- ベース: `python@sha256:285a71327884a4d50efbea30104473b0fa43ecefa499458899670ca30dae76e5`（Alpine 3.24.1、Python 3.12.14、`ca-certificates-20260611-r0`、G3 あり、AAA なし）
- この Dockerfile は `/tmp` にだけ置き、リポジトリには入れていない

試した手順:

1. `docker tag plaude-web:sec021-rehearsal-before plaude-web:sec021-rollback`
2. `docker save plaude-web:sec021-rollback -o /tmp/plaude-web-sec021-rollback.tar`  
   18,264,576 bytes、SHA-256 `c4958cab3c7578f01534961973268612113f50cf48120a68334874fe557abbf0`  
   この tar は検証環境の中だけにあり、本番の戻し用ではない
3. 修正後イメージを `latest` にして起動。image id は修正後、G3 は absent、API は ok
4. `docker tag plaude-web:sec021-rollback plaude-web:latest` のあと `docker compose up -d --no-build --pull never --force-recreate`。再作成されたコンテナの image id は代理の旧イメージと一致し、G3 は present、AAA は absent、`/healthz` と主要 API は ok
5. `docker rmi plaude-web:sec021-rollback` で tag だけ外し、`docker load -i` で同じ image id の tag が戻った
6. 修正後イメージを `latest` に戻して再作成し、G3 が再び absent であることと `/healthz` を確認してから `docker compose down` した

戻しはイメージの tag と起動であり、`~/plaude/data` には触れていない。再作成はコンテナを入れ替えるので、本番で同じ操作をすると origin は一度止まる。

## 本番配備の手順

承認が出てから、MS-A2 上で行う。ここには実行結果を書かない。`~/plaude/data` は同期しない。ビルドコンテキストに会議本文を入れない（`.dockerignore` の `data/`）。

1. いま動いているイメージを記録し、再起動する前に退避する。

```bash
ssh kite@192.168.1.2 'docker image inspect -f "{{.Id}}" plaude-web:latest'
ssh kite@192.168.1.2 'docker tag plaude-web:latest plaude-web:sec021-rollback-20261022'
ssh kite@192.168.1.2 'docker save plaude-web:sec021-rollback-20261022 -o ~/plaude-web-sec021-rollback-20261022.tar'
```

tar は `~/plaude/data` の中に置かない。`docker image inspect` の Id を控える。tag と tar の両方が戻し元である。

2. Mac で `web/` をビルドし、既存の rsync / scp で `web/dist`、`web-server`、`templates`、`Dockerfile`、`.dockerignore`、`docker-compose.yml` を `~/plaude/` に置く。`data/` は送らない。

3. コンテナを入れ替える前に、イメージだけ組む。

```bash
ssh kite@192.168.1.2 'cd ~/plaude && docker compose build'
```

`docker compose up -d --build` は build と再起動を同時に行う。検査が終わるまで使わない。build は `dl-cdn.alpinelinux.org` の apk index を取りにいく。届かなければビルドは失敗する（別の版へ黙って進まない）。

4. 動いているコンテナはそのままに、新しいイメージを検査する。`docker run` は `18880` の本番コンテナを止めない。

```bash
ssh kite@192.168.1.2 'docker run --rm --entrypoint python plaude-web:latest /app/web-server/sec021_trust_check.py'
ssh kite@192.168.1.2 'docker run --rm --entrypoint sh plaude-web:latest -c "apk list -I | grep ca-certificates"'
ssh kite@192.168.1.2 'docker run --rm --entrypoint python plaude-web:latest -c "import urllib.request; print(urllib.request.urlopen(\"https://example.com/\", timeout=30).status)"'
```

期待は `sec021 ca bundle` の行、`ca-certificates-20261020-r0` と `ca-certificates-bundle-20261020-r0`、HTTPS の `200`。検査スクリプトが非ゼロなら、ここで止めて本番コンテナは触らない。

5. 本番データとは別のモックで、本番ポート以外に一度起動する。モックは repo の `data/meetings/mock-safety` を一時ディレクトリへコピーしたものでよい。本番の `~/plaude/data` はマウントしない。

```bash
ssh kite@192.168.1.2 'docker run --rm -p 127.0.0.1:18881:8080 -v /tmp/plaude-sec021-mock:/data plaude-web:latest'
```

別シェルで `curl -fsS http://127.0.0.1:18881/healthz` と `/api/meetings`。モックだけが見え、本番の会議 id が出ないこと。

6. 承認された切替ウィンドウで、本番ボリュームのまま入れ替える。

```bash
ssh kite@192.168.1.2 'cd ~/plaude && docker compose up -d --no-build --pull never --force-recreate'
ssh kite@192.168.1.2 'docker inspect -f "{{.Image}}" plaude-web'
ssh kite@192.168.1.2 'curl -fsS http://127.0.0.1:18880/healthz'
```

`docker inspect` の Id が、手順 3 で組んだイメージと一致すること。Access、Tunnel、Caddy の設定は変えない。

## 本番の戻し手順

新しいコンテナの health が失敗したとき、または承認者が戻すと言ったときに行う。再ビルドしない。`~/plaude/data` は残す。

```bash
ssh kite@192.168.1.2 'docker tag plaude-web:sec021-rollback-20261022 plaude-web:latest'
ssh kite@192.168.1.2 'cd ~/plaude && docker compose up -d --no-build --pull never --force-recreate'
ssh kite@192.168.1.2 'docker inspect -f "{{.Image}}" plaude-web'
ssh kite@192.168.1.2 'curl -fsS http://127.0.0.1:18880/healthz'
```

Id が手順 1 で控えた値と一致すること。tag が消えていた場合は、同じホストの tar から戻す。

```bash
ssh kite@192.168.1.2 'docker load -i ~/plaude-web-sec021-rollback-20261022.tar'
```

load のあと、上の tag と `compose up --no-build` を繰り返す。戻したあとの信頼ストアには G3 が戻る。それは切り戻しの結果であり、修正の維持ではない。

## 本番で要る承認

次が揃うまで、MS-A2 では build も `compose up` もしない。

1. この準備を本番へ載せてよいかの明示の GO。PR のマージだけでは GO にしない
2. 切替のあいだ origin（`192.168.1.2:18880`）が一度止まることの了承。Access の外には出さない
3. 手順 1 の image id と、tag および tar の保存場所が記録されていること。tar が `~/plaude/data` の外にあること
4. 手順 4 の根照合と外向き HTTPS、手順 5 のモック起動が、本番コンテナを止める前に通っていること
5. 失敗したときは手順「本番の戻し」へ戻すこと。新しいイメージのままにしない
6. `emSign Root CA - G1` は束に残ることの了承。今回外すのは G3 と AAA Certificate Services である
7. 本番の録音、トークン、`~/plaude/data` をイメージやこのリポジトリへ入れないこと

## 準備できた範囲

- OS の確認（Alpine Linux 3.24.3）と修正版 `20261020-r0` の選択
- ベースの manifest list と apk 版の固定、ビルド時の根照合
- 修正後イメージでの (a)(b)(c)(d)
- 代理の旧イメージでの退避と戻し (e)
- 上の本番手順と戻し手順、承認条件

## 足りないもの

- 本番コンテナの現行 image id。SSH していないので未取得
- MS-A2 で組み直したあとの image id。ローカルの `sha256:3151ecd0…` は本番の id ではない
- Mac で組んだ `web/dist` でのイメージ。ここでの起動試験は、この環境の `npm run build` である
- Access、Tunnel、Caddy 経由の確認
- Plaud の presigned URL への音声 pull
- 本番ホスト上の実イメージを使った戻し。試した旧イメージは公開の修正前 Python イメージから組んだ代理である
- `20261020-r0` より新しい apk 改訂。出た場合は同じ根照合のあとで版のピンを上げる
