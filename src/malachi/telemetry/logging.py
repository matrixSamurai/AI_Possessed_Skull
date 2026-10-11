import json
import logging
import time


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


def configure_logging(debug=False):
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("malachi")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
