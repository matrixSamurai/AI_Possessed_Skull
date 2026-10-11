import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from malachi.config import Settings
from malachi.events import Face


@pytest.fixture
def settings():
    return Settings(_env_file=None)


@pytest.fixture
def face():
    return Face(
        track_id=1,
        center_x=0.5,
        center_y=0.5,
        box=(0.3, 0.2, 0.7, 0.8),
        yaw=0,
        pitch=0,
        confidence=0.9,
    )
