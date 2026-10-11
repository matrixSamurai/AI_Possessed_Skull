import base64
import hashlib
import importlib.util
import io
from pathlib import Path
from unittest.mock import patch
import zipfile
import pytest


@pytest.fixture
def downloader(tmp_path):
    path = Path(__file__).resolve().parents[1] / "scripts/download_model.py"
    spec = importlib.util.spec_from_file_location("download_model", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.TARGET = tmp_path / "face.task"
    module.MANIFEST = tmp_path / "face.task.sha256"
    return module


def response(valid=True):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("test-model.tflite", b"synthetic test fixture")
    data = stream.getvalue()
    stream.seek(0)
    md5 = hashlib.md5(data, usedforsecurity=False).digest() if valid else bytes(16)
    stream.headers = {"x-goog-hash": "md5=" + base64.b64encode(md5).decode()}
    return stream


def test_checksum_archive_and_repeatability(downloader):
    with patch("urllib.request.urlopen", return_value=response()) as request:
        downloader.main()
        downloader.main()
        assert request.call_count == 1
    assert downloader.TARGET.is_file() and downloader.MANIFEST.is_file()


def test_checksum_failure_does_not_install(downloader):
    with patch("urllib.request.urlopen", return_value=response(False)):
        with pytest.raises(RuntimeError, match="checksum"):
            downloader.main()
    assert not downloader.TARGET.exists()


def test_repeated_google_checksum_headers(downloader):
    from email.message import Message

    stream = response()
    data = stream.getvalue()
    headers = Message()
    headers.add_header(
        "x-goog-hash", "crc32c=" + base64.b64encode(downloader.crc32c(data)).decode()
    )
    headers.add_header("x-goog-hash", stream.headers["x-goog-hash"])
    stream.headers = headers
    with patch("urllib.request.urlopen", return_value=stream):
        downloader.main()
    assert downloader.TARGET.exists()


def test_crc32c_known_vector_and_crc_only_response(downloader):
    assert downloader.crc32c(b"123456789").hex() == "e3069283"
    stream = response()
    stream.headers = {
        "x-goog-hash": "crc32c=" + base64.b64encode(downloader.crc32c(stream.getvalue())).decode()
    }
    with patch("urllib.request.urlopen", return_value=stream):
        downloader.main()
    assert downloader.TARGET.exists()


def test_missing_checksums_still_rejected(downloader):
    stream = response()
    stream.headers = {}
    with patch("urllib.request.urlopen", return_value=stream):
        with pytest.raises(RuntimeError, match="checksum unavailable"):
            downloader.main()
    assert not downloader.TARGET.exists()


def test_bad_crc32c_still_rejected(downloader):
    stream = response()
    stream.headers = {"x-goog-hash": "crc32c=AAAAAA=="}
    with patch("urllib.request.urlopen", return_value=stream):
        with pytest.raises(RuntimeError, match="checksum failed"):
            downloader.main()
    assert not downloader.TARGET.exists()
