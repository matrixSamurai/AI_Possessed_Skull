# Detection-triggered scary background voices

MALACHI plays short effects when a face or sustained scene motion is detected.
Fresh-effects mode generates one new ElevenLabs effect per burst while cached clips
provide immediate playback. Local-only mode shuffles previously generated WAV clips.

## Sound effect: whispering ghost wail

For nonverbal wails/whispers, use the sound-effects generator rather than TTS voice IDs:

```sh
python -m malachi.ambience.generate_effects \
  --prompt "Whispering ghost wail" --duration 5 --variations 3
```

This uses your existing ELEVENLABS_API_KEY and the official ElevenLabs sound-effects
API (`eleven_text_to_sound_v2`), generating three cached variations with no voice ID.
The prompt asks for atmospheric nonverbal horror ambience without intelligible speech
or music. Actual style/quality must be auditioned locally. Generation uses sound-effect
credits; cached playback itself uses no API calls. Fresh-effects mode additionally
requests a new effect for each burst. Each request has no automatic
retries and a 60-second timeout; WAV output is validated, bounded and cached.

The name is a **generation description**, not an identifier for downloading an existing
saved effect. If you want the exact already-created "whispering ghost wail" clip, download
its audio from ElevenLabs and provide it as a supported local WAV. MP3 files need conversion
to 16 kHz mono PCM16 WAV before the existing player can load them. No new file-fetch API
or sound-library identifier is invented from the title.

## Generate clips with your existing ElevenLabs key

```sh
git pull origin main
source .venv/bin/activate
python -m malachi.ambience.generate \
  --voice-id YOUR_SCARY_VOICE_ID \
  --phrase "Who dares enter?" \
  --phrase "Do you hear them?" \
  --phrase "Stay a little longer."
```

Repeat `--voice-id` to use several voices. Each voice/phrase combination becomes a
cached WAV; at most 16 combinations are allowed per command. Phrases are limited to
200 characters and output to 30 seconds. The command uses ElevenLabs TTS credits,
not an ElevenAgents conversational session. ELEVENLABS_API_KEY must have access to
those voices and TTS. Voice IDs are safe to share; API keys should stay in .env.

Without --phrase, three short preset phrases are used. The default TTS model is
`eleven_multilingual_v2`; choose another compatible PCM-capable model via --model
if desired. Scary delivery depends on the selected voice; the code does not guarantee
a scary tone from every voice or synthesize nonverbal sound effects.

Generated clips are stored in the ignored assets/ambience folder as hashed filenames.
Rerunning the same voice/phrase/model combinations validates and reuses them without
another API request. Invalid existing caches are not overwritten silently; remove
that invalid generated file intentionally before regenerating it. Clip generation
stops on a failed request; completed clips remain cached. API retries are disabled.

You may instead place existing audio clips in that directory. Supported format:
**16 kHz, mono, signed 16-bit PCM WAV**, at most 30 seconds per clip. At most 16 clips
are loaded; no MP3 decoder/converter is included. Loading happens on a worker.

## Runtime settings

Add to your existing .env, then restart the real app:

```dotenv
AMBIENCE_ENABLED=true
AMBIENCE_DIRECTORY=assets/ambience_library
AMBIENCE_DURATION_SECONDS=25
AMBIENCE_VOLUME=0.15
AMBIENCE_DURING_CONVERSATION=true
```

- Sustained face presence or scene motion for 300 ms triggers a 25-second playback
  window. AMBIENCE_DURATION_SECONDS accepts 20–30 seconds.
- Clips play in shuffled order with short randomized gaps; each clip is used before
  the shuffle bag repeats, including across new playback windows. Immediate repeats across bag boundaries are avoided when
  there are multiple clips.
- Clip endpoints and burst boundaries fade; background volume is separate from voice.
- Continuous detection does not extend a burst or immediately retrigger it. Three
  seconds without a face/motion rearms detection; after expiry there is a 10-second
  cooldown. These values are configurable in .env.
- The motion trigger uses frame differences, not semantic object recognition. It can
  respond to shadows/camera shake; global lighting changes are filtered heuristically.
  It does not identify or track specific moving objects. Tune MOTION_PIXEL_THRESHOLD
  and MOTION_AREA_THRESHOLD if required; it remains an approximate scene-motion signal.
- Camera stop/stale capture cannot start a new burst. An already triggered window may
  finish. Emergency Stop clears background playback and prevents retriggering until
  explicit resume. Mute speaker mutes background too. The Background voices checkbox
  can disable/re-enable it during a run when it was enabled at startup.
- Background voices never drive the skull jaw or count as agent speech/activity.

The dashboard reports readiness, missing clips, playback time and the conversation volume.
Missing/invalid files leave ordinary vision and conversations usable. --demo disables
real background audio. --vision-only can still play cached clips with the actual
camera if AMBIENCE_ENABLED=true; it requires no live voice session or TTS request.

## During conversation

Background effects now continue through AWAKENING, CONVERSING and ENDING at **30%
of the configured AMBIENCE_VOLUME**, including pauses between agent replies. Outside
conversation they use 100% of AMBIENCE_VOLUME. The gain changes smoothly. The usual
25-second burst remains active for the full conversation, then gets a fresh 25-second
window at normal volume before stopping. Set AMBIENCE_DURING_CONVERSATION=false if
you explicitly want conversation silence instead.

The Speaker echo guard remains available for the agent's own speech. Background PCM
does not drive the jaw, agent-speaking events, or a permanent microphone mute. It is
not acoustically echo-cancelled: MacBook microphones may still pick up background
effects. Keep the normal background level modest; headphones provide better isolation.
Idle-output handover retains its short acoustic-tail guard.

## Validation and remaining setup

Unit/integration tests cover detection hold, fixed window, nonrepeating triggers,
rearming/cooldown, shuffle, fades/ducking, mute/emergency stop, motion heuristics,
WAV validation, actual SDK TTS serialization through a mocked transport, cached reuse,
exclusive output handover and agent-jaw independence. No real TTS clips or audible
Mac playback were verified in the cloud (no credentials/audio devices).

Provide the desired voice IDs and phrases, or generate clips locally using the command
above. Until clips are present and ambience is enabled, the background system is quiet.
This feature does not resolve the separate ElevenLabs HTTP 400 image-upload rejection.

## Fresh effects for each burst

With `AMBIENCE_ENABLED=true`, `AMBIENCE_FRESH_EFFECTS_ENABLED=true` (opt-in)
and your existing ElevenLabs API key, each new ambience burst requests one new
five-second sound effect from ElevenLabs. A shuffled prompt bank rotates ghost
wails, spectral whispers, phantom moans, eerie laughter, hollow howls, haunted
wind, wordless spectral choirs, and haunted-door effects. This generates audio;
it does not browse or download a curated website collection.

Cached clips play immediately while generation runs in a separate worker. A fresh
effect is selected at the next clip boundary once available; slow generation may
make it available for a later burst. Empty banks request a bootstrap effect at startup.
One request runs at a time, overlapping requests coalesce, and the API is not retried
on failure. Generation uses ElevenLabs sound-effect credits. Playback remains subject
to the existing conversation volume setting, mute and emergency stop controls.

Generated WAVs use temporary storage and are deleted after decoding; a maximum of
16 clips remain in memory. Failed generation retains the existing clips. Set
`AMBIENCE_FRESH_EFFECTS_ENABLED=false` to return to local cached effects only.

## Included project collection

The 12 effects uploaded by the owner are committed in `assets/ambience_library`.
Original MP3s are preserved in its `originals/` subdirectory; ready-to-play WAVs
are converted to 16 kHz mono PCM16, capped at 30 seconds. This collection is the
default playback directory, with fresh generation disabled by default.

Existing installations must update their `.env` overrides:

```dotenv
AMBIENCE_ENABLED=true
AMBIENCE_DIRECTORY=assets/ambience_library
AMBIENCE_FRESH_EFFECTS_ENABLED=false
```

Restart after pulling. The shuffle bag uses the whole bank before repeating,
including across bursts. Conversation effects play at 30% of their configured
normal volume; mute and emergency stop still apply.
