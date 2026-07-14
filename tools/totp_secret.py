#!/usr/bin/env python3
"""Print the base32 TOTP secret(s) from an otpauth QR's text.

Scan the 2FA QR with any QR-reader app to get its text, then pass it here:

    python3 totp_secret.py 'otpauth://totp/...?secret=ABC...'
    python3 totp_secret.py 'otpauth-migration://offline?data=...'   # Google Authenticator export

- otpauth://       -> the secret is already base32; it's just printed back.
- otpauth-migration:// (Google Authenticator "export/transfer accounts") -> the secret is
  raw bytes inside a protobuf; this base32-encodes it for you.

Stdlib only. Nothing is sent anywhere.
"""

import base64
import sys
import urllib.parse


def _from_otpauth(url: str) -> list[tuple[str, str]]:
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    label = urllib.parse.unquote(urllib.parse.urlparse(url).path.lstrip("/")) or "account"
    return [(label, q["secret"][0])]


def _read_varint(b: bytes, i: int) -> tuple[int, int]:
    r = s = 0
    while True:
        x = b[i]
        i += 1
        r |= (x & 0x7F) << s
        s += 7
        if not x & 0x80:
            return r, i


def _fields(b: bytes):
    i = 0
    while i < len(b):
        tag, i = _read_varint(b, i)
        wt = tag & 7
        if wt == 0:
            v, i = _read_varint(b, i)
        elif wt == 2:
            ln, i = _read_varint(b, i)
            v, i = b[i : i + ln], i + ln
        else:
            raise ValueError(f"unsupported wire type {wt}")
        yield tag >> 3, v


def _from_migration(url: str) -> list[tuple[str, str]]:
    data = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["data"][0]
    raw = base64.b64decode(data + "=" * (-len(data) % 4))
    out = []
    for fn, v in _fields(raw):
        if fn != 1 or not isinstance(v, bytes):  # repeated OtpParameters
            continue
        secret = name = ""
        for f2, v2 in _fields(v):
            if not isinstance(v2, bytes):
                continue
            if f2 == 1:
                secret = base64.b32encode(v2).decode().rstrip("=")
            elif f2 == 2:
                name = v2.decode()
        out.append((name or "account", secret))
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 2
    url = argv[1].strip()
    if url.startswith("otpauth-migration://"):
        accounts = _from_migration(url)
    elif url.startswith("otpauth://"):
        accounts = _from_otpauth(url)
    else:
        print("error: not an otpauth:// or otpauth-migration:// URL", file=sys.stderr)
        return 1
    for name, secret in accounts:
        print(f"{name}: {secret}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
