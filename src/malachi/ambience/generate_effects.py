"""Explicit, cached ElevenLabs sound-effect generation, with no voice IDs."""

import argparse
import hashlib
from pathlib import Path
import tempfile
import wave
from malachi.config import Settings
from malachi.ambience.engine import RATE, read_clip

MODEL = "eleven_text_to_sound_v2"


def generate_effect(client, description, duration, variation, directory):
    if not description.strip() or len(description) > 500 or not 0.5 <= duration <= 30:
        raise ValueError("Use a 1–500 character description and 0.5–30 second duration")
    prompt = (
        description + ". Atmospheric nonverbal horror ambience; no intelligible "
        f"words or music. Variation {variation + 1}: subtle differences in pitch and texture."
    )
    identity = hashlib.sha256(f"{MODEL}\0{prompt}\0{duration:.3f}".encode()).hexdigest()[:16]
    target = directory / f"effect-{identity}.wav"
    if target.exists():
        read_clip(target)
        return target, False
    pcm = bytearray()
    for chunk in client.text_to_sound_effects.convert(
        text=prompt,
        model_id=MODEL,
        duration_seconds=duration,
        output_format="pcm_16000",
        prompt_influence=0.5,
        request_options={"max_retries": 0, "timeout_in_seconds": 60},
    ):
        pcm.extend(chunk)
        if len(pcm) > RATE * 30 * 2:
            raise ValueError("Returned effect exceeds 30 seconds")
    if not pcm or len(pcm) % 2:
        raise ValueError("Invalid PCM16 returned")
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=directory, delete=False, suffix=".tmp") as file:
        temporary = Path(file.name)
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
        description="Generate cached scary effects (uses ElevenLabs sound-effect credits)"
    )
    parser.add_argument("--prompt", default="Whispering ghost wail")
    parser.add_argument("--duration", type=float, default=5)
    parser.add_argument("--variations", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.variations <= 16:
        parser.error("Use 1–16 variations")
    if not 0.5 <= args.duration <= 30:
        parser.error("Use 0.5–30 seconds per effect")
    if not args.prompt.strip() or len(args.prompt) > 500:
        parser.error("Description must be 1–500 characters")
    settings = Settings()
    key = settings.elevenlabs_api_key.get_secret_value()
    if not key:
        parser.error("Set ELEVENLABS_API_KEY locally in .env")
    from elevenlabs.client import ElevenLabs
    import httpx

    made = cached = 0
    try:
        with httpx.Client(timeout=60) as transport:
            client = ElevenLabs(
                api_key=key, base_url="https://api.elevenlabs.io", httpx_client=transport
            )
            for variation in range(args.variations):
                _, created = generate_effect(
                    client, args.prompt, args.duration, variation, settings.ambience_directory
                )
                made += int(created)
                cached += int(not created)
    except Exception as exc:
        print(
            f"Effect generation stopped ({type(exc).__name__}); check sound-effect access and quota."
        )
        return 1
    print(
        f"{made} effects generated, {cached} cached effects reused. Enable AMBIENCE_ENABLED=true and restart."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
