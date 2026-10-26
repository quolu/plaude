#!/usr/bin/env python3
"""SEC021 の根照合が、修正前の G3 と AAA 根を証明書バイト列で拒否すること。"""
import ssl
import tempfile
from pathlib import Path

import sec021_trust_check as trust

ROOT = Path(__file__).resolve().parent
G3 = ROOT / "testdata" / "emSign_ECC_Root_CA_-_G3.pem"
AAA = ROOT / "testdata" / "AAACertificateServices.pem"


def bundle(pem: Path) -> Path:
    directory = Path(tempfile.mkdtemp())
    target = directory / "ca-certificates.crt"
    # 本数の下限より少なくても、禁止根は本数チェックより先に拒否する。
    target.write_bytes(pem.read_bytes())
    return target


def expect_banned(pem: Path, label: str) -> None:
    try:
        trust.check([bundle(pem)])
    except SystemExit as exc:
        message = str(exc)
        assert label in message, message
        return
    raise SystemExit(f"{label} was accepted")


def main() -> int:
    g3 = G3.read_bytes()
    aaa = AAA.read_bytes()
    assert trust.spki_sha256(ssl.PEM_cert_to_DER_cert(g3.decode())) == trust.EMSIGN_ECC_ROOT_CA_G3_SPKI
    assert trust.spki_sha256(ssl.PEM_cert_to_DER_cert(aaa.decode())) == trust.AAA_CERTIFICATE_SERVICES_SPKI
    expect_banned(G3, "emSign ECC Root CA - G3")
    expect_banned(AAA, "AAA Certificate Services")
    print("sec021 trust check rejects G3 and AAA")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
