"""One bounded worker generates a fresh effect for each ambience burst."""

import random
import tempfile
import threading
from pathlib import Path
from malachi.ambience.generate_effects import generate_effect
from malachi.ambience.engine import read_clip
from malachi.events import ConversationEvent

PROMPTS = (
    "Whispering ghost wail, airy and distant",
    "Layered spectral whispers drifting through a haunted room",
    "A low mournful phantom moan with cavernous echoes",
    "Faint eerie ghost laughter carried on a cold wind",
    "An otherworldly hollow howl slowly fading into darkness",
    "Haunted wind with soft ghostly sighs and rustling shadows",
    "A distant spectral choir of wordless wavering voices",
    "A creaking haunted doorway followed by a breathy ghost wail",
)


class FreshEffects:
    def __init__(self, settings, install, emit, generator=None):
        self.settings, self.install, self.emit = settings, install, emit
        self.generator = generator or self._generate
        self.pending = threading.Event()
        self.exit = threading.Event()
        self.bag = []
        self.last_prompt = None
        self.sequence = 0
        self.thread = threading.Thread(target=self._run, daemon=True, name="fresh-horror-effects")
        self.thread.start()

    def request(self):
        # Requests coalesce: never build a queue of paid generations.
        self.pending.set()

    def _prompt(self):
        if not self.bag:
            self.bag = list(PROMPTS)
            random.shuffle(self.bag)
            if self.bag[-1] == self.last_prompt:
                self.bag[0], self.bag[-1] = self.bag[-1], self.bag[0]
        self.last_prompt = self.bag.pop()
        return self.last_prompt

    def _generate(self, prompt, sequence):
        import httpx
        from elevenlabs.client import ElevenLabs

        # Temporary cache is removed after conversion; only bounded PCM remains.
        with tempfile.TemporaryDirectory(prefix="malachi-effect-") as directory:
            with httpx.Client(timeout=60) as transport:
                client = ElevenLabs(
                    api_key=self.settings.elevenlabs_api_key.get_secret_value(),
                    httpx_client=transport,
                )
                path, _ = generate_effect(client, prompt, 5, sequence, Path(directory))
                return read_clip(path)

    def _run(self):
        while not self.exit.is_set():
            if not self.pending.wait(0.1):
                continue
            self.pending.clear()
            if self.exit.is_set():
                return
            try:
                self.sequence += 1
                clip = self.generator(self._prompt(), self.sequence)
                if not self.exit.is_set():
                    self.install(clip)
                    self.emit(
                        ConversationEvent(
                            kind="summary", detail="Fresh ElevenLabs background effect ready"
                        )
                    )
            except Exception as exc:
                if not self.exit.is_set():
                    self.emit(
                        ConversationEvent(
                            kind="summary",
                            detail=f"Fresh background effect unavailable ({type(exc).__name__}); using cached effects",
                        )
                    )
            # A slow request does not accumulate another generation behind it.
            self.pending.clear()

    def close(self):
        self.exit.set()
        self.pending.set()
        self.thread.join(0.2)
