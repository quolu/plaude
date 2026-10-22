# python:3.12-alpine は 2026-10-22 時点でこの manifest list と同一。
# 確認した OS は Alpine Linux v3.24.3。linux/amd64 の image digest は
# sha256:9b98a8d37794ca093ba8d5afe1ffac52f5a15168b9b4e67594d86c20e14fa681。
# 本番 MS-A2（linux/amd64）もこの list から amd64 を取る。
FROM python:3.12.15-alpine3.24@sha256:92abd2ba1bdfb48b1e2ac224b582dd1558d0d4bb11c903b126b5bf9c448fd656

# SEC021: Alpine の修正版は ca-certificates 20261020-r0。
# 信頼束の実体は ca-certificates-bundle（/etc/ssl/certs/ca-certificates.crt）。
# 版を固定し、emSign ECC Root CA - G3 と AAA Certificate Services の
# 証明書 SHA-256 が束にも個別 PEM にも無いことをビルド時に拒否する。
# シェルの heredoc は BuildKit（docker compose build の既定）が要る。
RUN apk add --no-cache \
        "ca-certificates=20261020-r0" \
        "ca-certificates-bundle=20261020-r0" \
    && apk list -I | awk '$1=="ca-certificates-20261020-r0"{c=1} $1=="ca-certificates-bundle-20261020-r0"{b=1} END{exit !(c && b)}' \
    && python - <<'PY'
import hashlib
import pathlib
import ssl
import sys

# 根の証明書そのものの SHA-256。名前ではなく証明書バイト列で照合する。
# G3 は Mozilla 束 2026-09-25（curl cacert-2026-09-25.pem）から採取。
# AAA は Comodo の自己署名根 http://crt.comodoca.com/AAACertificateServices.crt。
banned = {
    "86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b",
    "d7a7a0fb5d7e2731d771e9484ebcdef71d5f0c3e0a2948782bc83ee0ea699ef4",
}
paths = [pathlib.Path("/etc/ssl/certs/ca-certificates.crt")]
paths += list(pathlib.Path("/usr/share/ca-certificates").rglob("*.crt"))
paths += list(pathlib.Path("/etc/ssl/certs").iterdir())
seen = set()
bundle_n = 0
for path in paths:
    try:
        data = path.read_bytes()
    except OSError:
        continue
    if b"-----BEGIN CERTIFICATE-----" not in data:
        continue
    for part in data.split(b"-----END CERTIFICATE-----"):
        start = part.find(b"-----BEGIN CERTIFICATE-----")
        if start < 0:
            continue
        pem = part[start:] + b"-----END CERTIFICATE-----\n"
        fp = hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem.decode())).hexdigest()
        if fp in banned:
            sys.exit(f"banned root {fp} in {path}")
        seen.add(fp)
        if path.name == "ca-certificates.crt":
            bundle_n += 1
if bundle_n < 100:
    sys.exit(f"ca bundle too small: {bundle_n}")
print(f"sec021 ca bundle {bundle_n} unique {len(seen)}")
PY

WORKDIR /app
COPY web/dist /app/web/dist
COPY web-server /app/web-server
COPY templates /app/templates
ENV PLAUDE_BIND=0.0.0.0
ENV PLAUDE_PORT=8080
ENV PLAUDE_DATA_DIR=/data
ENV PLAUDE_STATIC_DIR=/app/web/dist
EXPOSE 8080
CMD ["python", "/app/web-server/server.py"]
