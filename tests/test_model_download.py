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
