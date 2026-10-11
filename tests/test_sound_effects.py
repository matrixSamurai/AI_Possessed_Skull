import json
import numpy as np
import pytest
from malachi.ambience.generate_effects import generate_effect
from malachi.ambience.engine import read_clip


def test_actual_sound_effect_sdk_and_cached_reuse(tmp_path):
    import httpx
    from elevenlabs.client import ElevenLabs

    requests = []

    def handle(request):
        requests.append(request)
        assert request.url.path == "/v1/sound-generation"
        assert request.url.params["output_format"] == "pcm_16000"
        body = json.loads(request.content)
        assert body["text"].startswith("Whispering ghost wail")
        assert "no intelligible words" in body["text"]
        assert body["duration_seconds"] == 5
        assert body["model_id"] == "eleven_text_to_sound_v2"
        return httpx.Response(200, content=np.full(1600, 3000, dtype="<i2").tobytes())

    with httpx.Client(transport=httpx.MockTransport(handle)) as transport:
        client = ElevenLabs(api_key="test-key", httpx_client=transport)
        path, made = generate_effect(client, "Whispering ghost wail", 5, 0, tmp_path)
        assert made and len(read_clip(path)) == 1600
        _, made = generate_effect(client, "Whispering ghost wail", 5, 0, tmp_path)
        assert not made
        other, made = generate_effect(client, "Whispering ghost wail", 5, 1, tmp_path)
        assert made and other != path
    assert len(requests) == 2


def test_invalid_effect_parameters_never_make_request(tmp_path):
    for prompt, duration in [("", 5), ("x" * 501, 5), ("ghost", 0), ("ghost", 31)]:
        with pytest.raises(ValueError):
            generate_effect(None, prompt, duration, 0, tmp_path)
