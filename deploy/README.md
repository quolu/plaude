# plaud.kitepon.dev

```
Cloudflare Access → Tunnel home-server (168cebb0-a0e2-44c8-bfdc-d4a91a1ccbfb)
  → Caddy → 192.168.1.2:18880 → plaude-web
```

## コンテナ

**npm build だけ Mac で行い、image は MS-A2 で組む。** image の中身は `web/dist` と Python だけなので、
MS-A2 側の build は数秒で終わる（重いのは npm であって docker ではない）。Mac 側で
cross-arch build（`buildx --platform linux/amd64`）をする必要はない。

```bash
cd web && npm ci && npm run build && cd ..
rsync -a web/dist/     kite@192.168.1.2:~/plaude/web/dist/
rsync -a --exclude '__pycache__' web-server/ kite@192.168.1.2:~/plaude/web-server/
rsync -a templates/    kite@192.168.1.2:~/plaude/templates/
scp Dockerfile .dockerignore docker-compose.yml kite@192.168.1.2:~/plaude/
ssh kite@192.168.1.2 'cd ~/plaude && docker compose up -d --build'
```

**`~/plaude/data` を同期対象にしない。** そこは実データの volume であり、repo の `data/` は
モック fixture である。`.dockerignore` で `data/` を build context から外してあるので、
会議本文が image に焼き込まれることもない（実行時は `/data` の volume だけを読む）。

確認:

```bash
ssh kite@192.168.1.2 'curl -s http://127.0.0.1:18880/healthz'
ssh kite@192.168.1.2 'curl -sI http://127.0.0.1:18880/m/<id>/transcript.txt'   # attachment; filename="<id>-transcript.txt"
ssh kite@192.168.1.2 'curl -sI http://127.0.0.1:18880/m/<id>/summary.md'       # attachment; filename="<id>-summary.md"
ssh kite@192.168.1.2 'docker run --rm --entrypoint sh plaude-web:latest -c "ls /app"'   # data が無いこと
```

## Caddy

`deploy/caddy-plaud.kitepon.dev.txt` を `>> /home/kite/license-server/Caddyfile`。inode を変えない。`docker exec caddy caddy reload --config /etc/caddy/Caddyfile`。効かなければ `docker restart caddy`。

## Tunnel / DNS / Access

ingress は GET してから `plaud.kitepon.dev` → `https://caddy:443` を catch-all 直前へ PUT。
CNAME `plaud` → `168cebb0-a0e2-44c8-bfdc-d4a91a1ccbfb.cfargotunnel.com`（proxied）。
Access は `afk.kitepon.dev` と同じく `kitepon@gmail.com` のみ。
