import pytest
from pydantic import ValidationError
from malachi.config import Settings


def test_validation_and_secret_redaction():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, face_facing_hold_seconds=-1)
    s = Settings(_env_file=None, elevenlabs_api_key="example-test-value")
    assert "example-test-value" not in repr(s)
    assert s.motion_backend == "simulation"


def test_default_visitor_absence_grace_is_twenty_seconds():
    assert Settings(_env_file=None).visitor_absence_timeout_seconds == 20
