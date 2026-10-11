# Existing ElevenAgents ghost agent

1. Keep your existing agent, custom ghost voice and first message in ElevenLabs.
2. Install the `conversation` extra. The application uses official `elevenlabs==2.71.0`
   for `client.conversational_ai.conversations.get_signed_url(agent_id=...)`.
3. Enter ELEVENLABS_AGENT_ID and ELEVENLABS_API_KEY in your local ignored `.env`.
   Never send a key in chat or include it in Git. The UI exposes agent ID, never the key.
4. Set CONVERSATION_BACKEND=elevenlabs. Input and output must negotiate `pcm_16000`
   (signed 16-bit little-endian PCM, mono, 16 kHz). Unsupported formats stop before streaming.
5. Use headphones; verify macOS microphone/camera permissions and default devices.
6. Launch `malachi`. A face qualifies after the hold or use Start session manually.
   The existing agent sends its greeting; the application does not create or overwrite it.
7. Verify the remote-stream indicator, real greeting, conversation and jaw timing.
   Walk away for 10 seconds; check that streaming stops and state becomes COOLDOWN.

Official references:
- https://elevenlabs.io/docs/agents-platform/libraries/python
- https://elevenlabs.io/docs/agents-platform/libraries/web-sockets
- https://elevenlabs.io/docs/agents-platform/api-reference/agents-platform/websocket

The adapter was cross-checked against the installed official SDK's AudioInterface
format contracts and message handlers. It uses documented conversation initiation,
metadata, base64 audio, user transcript, agent response, interruption and ping/pong
messages. It maintains one socket for the session. Async sends are bridged from a
bounded microphone sender queue. Metadata is required before audio starts.
The SDK does not provide the required playback timestamp control, so our application
owns PortAudio playback and consumes WebSocket audio directly.

Only summaries of event types are shown; transcript text is used transiently for
whole-utterance goodbye detection and discarded. Signed URLs and keys never enter
logs. Local logging is console-only. Review agent retention/privacy settings separately;
remote service recordings are not governed by the local default.

Cloud sessions require network access to api.elevenlabs.io and a suitable credential
binding, plus real input/output devices. The current cloud task has no devices or
credentials and did **not** make a live conversational request. Proxy-based cloud
credentials may not behave like a local raw key; verify the supported signed-URL and
WebSocket route separately before relying on them. Keep live testing on the Mac for now.
