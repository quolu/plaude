# plaud.kitepon.dev

```
Cloudflare Access → Tunnel home-server (168cebb0-a0e2-44c8-bfdc-d4a91a1ccbfb)
  → Caddy → 192.168.1.2:18880 → plaude-web
```

## コンテナ

Mac で `web/` を build してから image を送る。MS-A2 上で重い build はしない。

```bash
cd web && npm ci && npm run build && cd ..
docker buildx build --platform linux/amd64 -t plaude-web:latest .
docker save plaude-web:latest | ssh kite@192.168.1.2 docker load
scp docker-compose.yml docker-compose.override.yml.example kite@192.168.1.2:~/plaude/
ssh kite@192.168.1.2 'mkdir -p ~/plaude/data && cd ~/plaude && cp -n docker-compose.override.yml.example docker-compose.override.yml; docker compose up -d'
```

## Caddy

`deploy/caddy-plaud.kitepon.dev.txt` を `>> /home/kite/license-server/Caddyfile`。inode を変えない。`docker exec caddy caddy reload --config /etc/caddy/Caddyfile`。効かなければ `docker restart caddy`。

## Tunnel / DNS / Access

ingress は GET してから `plaud.kitepon.dev` → `https://caddy:443` を catch-all 直前へ PUT。
CNAME `plaud` → `168cebb0-a0e2-44c8-bfdc-d4a91a1ccbfb.cfargotunnel.com`（proxied）。
Access は `afk.kitepon.dev` と同じく `kitepon@gmail.com` のみ。
