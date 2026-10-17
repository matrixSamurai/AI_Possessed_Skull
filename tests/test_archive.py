import json
import logging
import os

import cv2
import numpy as np

from malachi.telemetry.archive import CameraArchive, prune
from malachi.telemetry.logging import configure_logging


def test_retention_only_deletes_owned_expired_files(tmp_path):
    names = ["malachi-image-old.jpg", "malachi-events-old.jsonl.2020", "notes.txt"]
    for name in names:
        path = tmp_path / name
        path.write_text("old")
        os.utime(path, (1, 1))
    fresh = tmp_path / "malachi-image-new.jpg"
    fresh.write_text("fresh")
    outside = tmp_path / "outside.jpg"
    outside.write_text("keep")
    (tmp_path / "malachi-image-link.jpg").symlink_to(outside)
    prune(tmp_path, 3 * 86400)
    assert not (tmp_path / names[0]).exists()
    assert not (tmp_path / names[1]).exists()
    assert (tmp_path / "notes.txt").exists()
    assert fresh.exists() and outside.exists()
    assert (tmp_path / "malachi-image-link.jpg").is_symlink()


def test_capture_saves_valid_jpeg_and_skips_missing_frame(settings, tmp_path):
    settings.log_directory = tmp_path
    frame = np.full((32, 64, 3), 80, np.uint8)
    archive = CameraArchive(settings, lambda: frame)
    archive.capture()
    paths = list(tmp_path.glob("*.jpg"))
    assert len(paths) == 1
    assert cv2.imread(str(paths[0])).shape == frame.shape
    archive.snapshot = lambda: None
    archive.capture()
    assert len(list(tmp_path.glob("*.jpg"))) == 1


def test_file_logging_and_rollover_prune(tmp_path):
    logger = logging.getLogger("malachi")
    previous = list(logger.handlers)
    logger.handlers = []
    try:
        configure_logging(directory=tmp_path)
        logger.info("archive test")
        path = next(tmp_path.glob("*.jsonl"))
        assert json.loads(path.read_text())["message"] == "archive test"
        old = tmp_path / "malachi-image-expired.jpg"
        old.write_bytes(b"old")
        os.utime(old, (1, 1))
        logger.handlers[-1].doRollover()
        assert not old.exists()
        logger.info("after rollover")
        assert json.loads(path.read_text())["message"] == "after rollover"
    finally:
        for handler in logger.handlers:
            handler.close()
        logger.handlers = previous
