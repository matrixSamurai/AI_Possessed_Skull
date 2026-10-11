"""Download Google's versioned Face Landmarker with TLS and upstream MD5 validation."""

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


def main():
    if TARGET.is_file() and MANIFEST.is_file():
        expected = MANIFEST.read_text().strip()
        if hashlib.sha256(TARGET.read_bytes()).hexdigest() == expected:
            print("Face Landmarker v1 already installed and verified")
            return
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(URL, timeout=60) as response:
        hashes = dict(
            part.strip().split("=", 1)
            for part in response.headers.get("x-goog-hash", "").split(",")
            if "=" in part
        )
        if "md5" not in hashes:
            raise RuntimeError("Upstream checksum unavailable; model was not installed")
        data = response.read(10_000_001)
        if len(data) > 10_000_000:
            raise RuntimeError("Unexpected model size")
        expected_md5 = base64.b64decode(hashes["md5"])
        if hashlib.md5(data, usedforsecurity=False).digest() != expected_md5:
            raise RuntimeError("Model checksum failed")
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
