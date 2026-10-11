"""Download Google's versioned Face Landmarker with TLS and upstream checksum validation."""

import base64
import hashlib
from pathlib import Path
import tempfile
import urllib.request
import zipfile

URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "assets/face_landmarker.task"
MANIFEST = TARGET.with_suffix(".task.sha256")


def crc32c(data: bytes) -> bytes:
    """Google Storage CRC32C (Castagnoli), encoded as four big-endian bytes."""
    table = []
    for value in range(256):
        for _ in range(8):
            value = (value >> 1) ^ (0x82F63B78 if value & 1 else 0)
        table.append(value)
    value = 0xFFFFFFFF
    for byte in data:
        value = table[(value ^ byte) & 0xFF] ^ (value >> 8)
    return (value ^ 0xFFFFFFFF).to_bytes(4, "big")


def main():
    if TARGET.is_file() and MANIFEST.is_file():
        expected = MANIFEST.read_text().strip()
        if hashlib.sha256(TARGET.read_bytes()).hexdigest() == expected:
            print("Face Landmarker v1 already installed and verified")
            return
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(URL, timeout=60) as response:
        # urllib's get() returns only the first occurrence of a repeated header.
        headers = response.headers
        values = (
            headers.get_all("x-goog-hash", [])
            if hasattr(headers, "get_all")
            else [headers.get("x-goog-hash", "")]
        )
        hashes = dict(
            part.strip().split("=", 1)
            for value in values
            for part in value.split(",")
            if "=" in part
        )
        available = set(hashes) & {"md5", "crc32c"}
        if not available:
            raise RuntimeError("Upstream checksum unavailable; model was not installed")
        data = response.read(10_000_001)
        if len(data) > 10_000_000:
            raise RuntimeError("Unexpected model size")
        # Verify every recognized checksum supplied over the trusted TLS connection.
        for name in available:
            expected = base64.b64decode(hashes[name], validate=True)
            actual = (
                hashlib.md5(data, usedforsecurity=False).digest() if name == "md5" else crc32c(data)
            )
            if actual != expected:
                raise RuntimeError(f"Model checksum failed ({name})")
    with tempfile.NamedTemporaryFile(dir=TARGET.parent, delete=False) as temporary:
        temporary.write(data)
        path = Path(temporary.name)
    try:
        if not zipfile.is_zipfile(path):
            raise RuntimeError("Invalid Face Landmarker task archive")
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise RuntimeError("Corrupt model archive")
        path.replace(TARGET)
        MANIFEST.write_text(hashlib.sha256(data).hexdigest() + "\n")
    finally:
        path.unlink(missing_ok=True)
    print("Installed and verified Google Face Landmarker v1")


if __name__ == "__main__":
    main()
