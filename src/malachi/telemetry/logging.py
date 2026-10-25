import json
import logging
import time
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler

from malachi.telemetry.archive import prune


class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(
            {
                "time": time.time(),
                "level": record.levelname,
                "component": record.name,
                "message": record.getMessage(),
            }
        )


class RetainedFileHandler(TimedRotatingFileHandler):
    def doRollover(self):
        super().doRollover()
        prune(self.archive_directory, self.retention_seconds)


def configure_logging(debug=False, directory=None, retention_days=3):
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("malachi")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    for old in list(logger.handlers):
        logger.removeHandler(old)
        old.close()
    logger.addHandler(handler)
    if directory is not None:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        prune(directory, retention_days * 86400)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        file_handler = RetainedFileHandler(
            directory / f"malachi-events-{stamp}.jsonl",
            when="M",
            interval=1,
            backupCount=0,
            encoding="utf-8",
            utc=True,
        )
        file_handler.archive_directory = directory
        file_handler.retention_seconds = retention_days * 86400
        file_handler.setFormatter(JsonFormatter())
        logger.addHandler(file_handler)
    logger.propagate = False
