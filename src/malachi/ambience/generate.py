"""Explicit one-time ElevenLabs TTS generation; runtime detection uses cached WAVs."""

import argparse
import hashlib
from pathlib import Path
import tempfile
import wave
from malachi.config import Settings
from malachi.ambience.engine import read_clip, RATE

DEFAULT_PHRASES = [
    "Do you hear them?",
    "Stay a little longer.",
    "Something is moving in the shadows.",
]


def generate_clip(client, voice_id, phrase, model, directory):
    identity = hashlib.sha256((voice_id + "\0" + phrase + "\0" + model).encode()).hexdigest()[:16]
    target = directory / f"voice-{identity}.wav"
    if target.exists():
        read_clip(target)  # Never overwrite an existing unverified/invalid file silently.
        return target, False
    pcm = bytearray()
    for chunk in client.text_to_speech.convert(
        voice_id=voice_id,
        text=phrase,
        model_id=model,
        output_format="pcm_16000",
        request_options={"max_retries": 0, "timeout_in_seconds": 30},
    ):
        pcm.extend(chunk)
        if len(pcm) > RATE * 30 * 2:
            raise ValueError("Clip exceeds 30 seconds; shorten the phrase")
    if not pcm or len(pcm) % 2:
        raise ValueError("Invalid PCM16 returned")
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=directory, delete=False, suffix=".tmp") as temp:
        temporary = Path(temp.name)
    try:
        with wave.open(str(temporary), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(RATE)
            wav.writeframes(pcm)
        read_clip(temporary)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target, True


def main():
    parser = argparse.ArgumentParser(
        description="Generate cached scary voice clips (uses ElevenLabs TTS credits)"
    )
    parser.add_argument(
        "--voice-id", action="append", required=True, help="Repeat for multiple ElevenLabs voices"
    )
    parser.add_argument("--phrase", action="append", help="Repeat for multiple short phrases")
    parser.add_argument("--model", default="eleven_multilingual_v2")
    args = parser.parse_args()
    phrases = args.phrase or DEFAULT_PHRASES
    voices = list(dict.fromkeys(args.voice_id))
    if len(voices) * len(phrases) > 16:
        parser.error("Use at most 16 voice/phrase combinations")
    if any(not p.strip() or len(p) > 200 for p in phrases):
        parser.error("Phrases must be 1–200 characters")
    settings = Settings()
    key = settings.elevenlabs_api_key.get_secret_value()
    if not key:
        parser.error("Set ELEVENLABS_API_KEY in your local .env")
    from elevenlabs.client import ElevenLabs
    import httpx

    made = cached = 0
    try:
        with httpx.Client(timeout=30) as transport:
            client = ElevenLabs(
                api_key=key, base_url="https://api.elevenlabs.io", httpx_client=transport
            )
            for voice in voices:
                for phrase in phrases:
                    _, created = generate_clip(
                        client, voice, phrase, args.model, settings.ambience_directory
                    )
                    made += int(created)
                    cached += int(not created)
    except Exception as exc:
        print(
            f"Clip generation stopped ({type(exc).__name__}); check key access, voice IDs and TTS quota."
        )
        return 1
    print(
        f"{made} clips generated, {cached} cached clips reused. Enable AMBIENCE_ENABLED=true and restart."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
