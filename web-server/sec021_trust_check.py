#!/usr/bin/env python3
"""SEC021: reject emSign ECC Root CA - G3 and AAA Certificate Services.

照合は表示名ではなく、証明書 DER の SHA-256 と SubjectPublicKeyInfo の SHA-256。
参照値は準備記録 docs/sec021-ca-certificates.md にある。
"""
from __future__ import annotations

import hashlib
import pathlib
import ssl
import sys

# emSign ECC Root CA - G3。Mozilla 束 2026-09-25 から採取した自己署名根。
EMSIGN_ECC_ROOT_CA_G3 = "86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b"
EMSIGN_ECC_ROOT_CA_G3_SPKI = "8d417db2dd8bf5e3084d1e3f196d583849d81bdd4c00c70b9d39369e96b8c782"
# AAA Certificate Services（Comodo）。公開されている自己署名根。
AAA_CERTIFICATE_SERVICES = "d7a7a0fb5d7e2731d771e9484ebcdef71d5f0c3e0a2948782bc83ee0ea699ef4"
AAA_CERTIFICATE_SERVICES_SPKI = "bd153ed7b0434f6886b17bce8bbe84ed340c7132d702a8f4fa318f756ecbd6f3"

BANNED_CERTS = {
    EMSIGN_ECC_ROOT_CA_G3: "emSign ECC Root CA - G3",
    AAA_CERTIFICATE_SERVICES: "AAA Certificate Services",
}
BANNED_SPKI = {
    EMSIGN_ECC_ROOT_CA_G3_SPKI: "emSign ECC Root CA - G3",
    AAA_CERTIFICATE_SERVICES_SPKI: "AAA Certificate Services",
}


def _read_tlv(data: bytes, index: int) -> tuple[int, bytes, bytes, int]:
    start = index
    tag = data[index]
    index += 1
    length = data[index]
    index += 1
    if length & 0x80:
        count = length & 0x7F
        if count == 0 or count > 4:
            raise ValueError("unsupported DER length")
        length = int.from_bytes(data[index : index + count], "big")
        index += count
    end = index + length
    if end > len(data):
        raise ValueError("truncated DER")
    return tag, data[index:end], data[start:end], end


def spki_sha256(der: bytes) -> str:
    tag, body, _, _ = _read_tlv(der, 0)
    if tag != 0x30:
        raise ValueError("certificate is not a SEQUENCE")
    tag, tbs, _, _ = _read_tlv(body, 0)
    if tag != 0x30:
        raise ValueError("tbsCertificate is not a SEQUENCE")
    index = 0
    if tbs[0] == 0xA0:
        _, _, _, index = _read_tlv(tbs, 0)
    for _ in range(5):
        _, _, _, index = _read_tlv(tbs, index)
    tag, _, tlv, _ = _read_tlv(tbs, index)
    if tag != 0x30:
        raise ValueError("subjectPublicKeyInfo is not a SEQUENCE")
    return hashlib.sha256(tlv).hexdigest()


def iter_pems(data: bytes):
    marker = b"-----BEGIN CERTIFICATE-----"
    for part in data.split(b"-----END CERTIFICATE-----"):
        start = part.find(marker)
        if start < 0:
            continue
        yield part[start:] + b"-----END CERTIFICATE-----\n"


def trust_paths() -> list[pathlib.Path]:
    bundle = pathlib.Path("/etc/ssl/certs/ca-certificates.crt")
    paths = [bundle]
    share = pathlib.Path("/usr/share/ca-certificates")
    if share.is_dir():
        paths += list(share.rglob("*.crt"))
    certs = pathlib.Path("/etc/ssl/certs")
    if certs.is_dir():
        paths += list(certs.iterdir())
    return paths


def check(paths: list[pathlib.Path]) -> tuple[int, int]:
    seen: set[str] = set()
    bundle_n = 0
    seen_paths: set[pathlib.Path] = set()
    for path in paths:
        try:
            key = path.resolve()
        except OSError:
            key = path
        if key in seen_paths:
            continue
        seen_paths.add(key)
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if b"-----BEGIN CERTIFICATE-----" not in data:
            continue
        for pem in iter_pems(data):
            der = ssl.PEM_cert_to_DER_cert(pem.decode())
            fingerprint = hashlib.sha256(der).hexdigest()
            spki = spki_sha256(der)
            if fingerprint in BANNED_CERTS:
                sys.exit(f"banned root {BANNED_CERTS[fingerprint]} fingerprint in {path}")
            if spki in BANNED_SPKI:
                sys.exit(f"banned root {BANNED_SPKI[spki]} spki in {path}")
            seen.add(fingerprint)
            if path.name == "ca-certificates.crt":
                bundle_n += 1
    if bundle_n < 100:
        sys.exit(f"ca bundle too small: {bundle_n}")
    return bundle_n, len(seen)


def main() -> int:
    bundle_n, unique = check(trust_paths())
    print(f"sec021 ca bundle {bundle_n} unique {unique}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
