# python:3.12-alpine は 2026-10-22 時点でこの manifest list と同一。
# 確認した OS は Alpine Linux v3.24.3。linux/amd64 の image digest は
# sha256:9b98a8d37794ca093ba8d5afe1ffac52f5a15168b9b4e67594d86c20e14fa681。
# 本番 MS-A2（linux/amd64）もこの list から amd64 を取る。
FROM python:3.12.15-alpine3.24@sha256:92abd2ba1bdfb48b1e2ac224b582dd1558d0d4bb11c903b126b5bf9c448fd656

# SEC021: Alpine の修正版は ca-certificates 20261020-r0。
# 信頼束の実体は ca-certificates-bundle（/etc/ssl/certs/ca-certificates.crt）。
# 版が違えば失敗する。続けて根の証明書 SHA-256 と SPKI SHA-256 を照合し、
# emSign ECC Root CA - G3 と AAA Certificate Services があれば失敗する。
RUN apk add --no-cache \
        "ca-certificates=20261020-r0" \
        "ca-certificates-bundle=20261020-r0" \
    && apk list -I | awk '$1=="ca-certificates-20261020-r0"{c=1} $1=="ca-certificates-bundle-20261020-r0"{b=1} END{exit !(c && b)}'
COPY web-server/sec021_trust_check.py /tmp/sec021_trust_check.py
RUN python /tmp/sec021_trust_check.py && rm /tmp/sec021_trust_check.py

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
