"""Documented ElevenAgents WebSocket protocol, signed URL from official SDK.

Reference: https://elevenlabs.io/docs/agents-platform/libraries/web-sockets
Only recognized documented events are consumed; no transcript is persisted.
"""

import asyncio
import base64
import json
from malachi.events import ConversationEvent


class ElevenLabsClient:
    def __init__(self, settings, playback, audio, emit, image_uploader=None):
        self.settings, self.playback, self.audio, self.emit = settings, playback, audio, emit
        self.snapshot = None
        self.image_uploader = image_uploader
        self.last_audio_received = None
        self.connected_at = None

    async def _deliver_snapshot(self, ws, conversation_id, stop):
        from malachi.vision.scene_context import ElevenLabsImageUploader, PHOTO_INSTRUCTIONS
        from elevenlabs.conversational_ai.conversation import (
            MultimodalMessageClientToOrchestratorEvent,
        )

        jpeg = self.snapshot.take() if self.snapshot is not None else None
        self.snapshot = None
        if not jpeg or stop.is_set():
            return
        try:
            self.emit(
                ConversationEvent(kind="scene", detail="Uploading one snapshot to ElevenLabs")
            )
            uploader = self.image_uploader or ElevenLabsImageUploader(self.settings)
            file_id = await asyncio.wait_for(
                uploader.upload(conversation_id, jpeg),
                timeout=self.settings.vision_context_timeout_seconds,
            )
            jpeg = None
            if stop.is_set():
                return
            self.emit(
                ConversationEvent(kind="scene", detail="Image uploaded; waiting for speech pause")
            )
            # A multimodal message is a conversation turn, so wait for the greeting/
            # current speech to drain rather than interrupting it with the photo.
            loop = asyncio.get_running_loop()
            deadline = loop.time() + self.settings.vision_context_delivery_wait_seconds
            while not stop.is_set():
                now = loop.time()
                pending = (
                    self.playback.samples > 0
                    or self.audio.agent_speaking
                    or self.audio.user_speaking
                )
                if self.last_audio_received is None:
                    settling = self.connected_at is not None and now - self.connected_at < 1.0
                else:
                    settling = now - self.last_audio_received < 0.35
                if not pending and not settling:
                    message = MultimodalMessageClientToOrchestratorEvent(
                        text=PHOTO_INSTRUCTIONS, file_ids=[file_id]
                    ).to_dict()
                    await asyncio.wait_for(ws.send(json.dumps(message)), timeout=2)
                    self.emit(
                        ConversationEvent(kind="scene", detail="Snapshot sent to ElevenLabs agent")
                    )
                    return
                if now >= deadline:
                    self.emit(
                        ConversationEvent(
                            kind="scene",
                            detail="Image delivery skipped: no speech pause; voice continues",
                        )
                    )
                    return
                await asyncio.sleep(0.05)
        except asyncio.TimeoutError:
            self.emit(
                ConversationEvent(
                    kind="scene", detail="Image upload/delivery timed out; voice continues"
                )
            )
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            status_hint = f" HTTP {status}" if status is not None else ""
            from malachi.conversation.upload_errors import upload_error_hint

            reason = upload_error_hint(exc, self.settings)
            hint = reason or "check agent file input, model and upload permissions"
            self.emit(
                ConversationEvent(
                    kind="scene",
                    detail=f"Image skipped ({type(exc).__name__}{status_hint}): {hint}",
                )
            )
        finally:
            jpeg = None

    async def run(self, stop):
        from elevenlabs.client import ElevenLabs
        from websockets.asyncio.client import connect

        key = self.settings.elevenlabs_api_key.get_secret_value()
        if not key or not self.settings.elevenlabs_agent_id:
            raise ValueError("Set ELEVENLABS_AGENT_ID and ELEVENLABS_API_KEY in local .env")
        client = ElevenLabs(api_key=key, timeout=10)
        signed = await asyncio.to_thread(
            client.conversational_ai.conversations.get_signed_url,
            agent_id=self.settings.elevenlabs_agent_id,
        )
        if stop.is_set():
            return
        async with connect(signed.signed_url, open_timeout=10, max_size=16 * 1024 * 1024) as ws:
            # Always supply a fallback so an agent prompt using {{visual_context}}
            # still works when analysis is disabled, unavailable or timed out.
            initiation = {
                "type": "conversation_initiation_client_data",
                "dynamic_variables": {
                    "visual_context": "A one-time camera image may arrive as an attachment. "
                    "Use the attached image once received; this placeholder is not a scene description. "
                    "Do not invent details if no image is available."
                },
            }
            await ws.send(json.dumps(initiation))
            loop = asyncio.get_running_loop()

            def send(audio):
                future = asyncio.run_coroutine_threadsafe(
                    ws.send(json.dumps({"user_audio_chunk": base64.b64encode(audio).decode()})),
                    loop,
                )
                future.result(timeout=2)

            snapshot_task = None
            try:
                last_interrupt_id = 0
                ready = False
                while not stop.is_set():
                    try:
                        message = json.loads(await asyncio.wait_for(ws.recv(), timeout=0.2))
                    except asyncio.TimeoutError:
                        continue
                    kind = message.get("type")
                    if kind == "conversation_initiation_metadata":
                        if ready:
                            raise ValueError("Duplicate session metadata")
                        meta = message["conversation_initiation_metadata_event"]
                        if (
                            meta.get("agent_output_audio_format") != "pcm_16000"
                            or meta.get("user_input_audio_format") != "pcm_16000"
                        ):
                            raise ValueError("Configure agent input and output as PCM 16000")
                        await asyncio.to_thread(self.audio.start, send)
                        ready = True
                        self.connected_at = loop.time()
                        self.emit(ConversationEvent(kind="connected"))
                        if self.snapshot is not None:
                            snapshot_task = asyncio.create_task(
                                self._deliver_snapshot(ws, meta["conversation_id"], stop)
                            )
                    elif kind == "audio":
                        if not ready:
                            raise ValueError("Audio received before session metadata")
                        if int(message["audio_event"]["event_id"]) <= last_interrupt_id:
                            continue
                        self.last_audio_received = loop.time()
                        self.playback.push(
                            base64.b64decode(message["audio_event"]["audio_base_64"])
                        )
                        self.emit(ConversationEvent(kind="activity"))
                    elif kind == "interruption":
                        last_interrupt_id = int(message["interruption_event"]["event_id"])
                        self.playback.clear(interrupted=True)
                        self.emit(ConversationEvent(kind="agent_end"))
                        self.emit(
                            ConversationEvent(
                                kind="summary",
                                detail="Agent interrupted; if unintended, check speaker echo",
                            )
                        )
                    elif kind == "ping":
                        await ws.send(
                            json.dumps(
                                {"type": "pong", "event_id": message["ping_event"]["event_id"]}
                            )
                        )
                    elif kind == "user_transcript":
                        text = (
                            message["user_transcription_event"]["user_transcript"].strip().lower()
                        )
                        self.emit(ConversationEvent(kind="activity"))
                        self.emit(
                            ConversationEvent(kind="summary", detail="Visitor transcript received")
                        )
                        # Conservative explicit whole-utterance intent, never substring matching.
                        if text.rstrip(".!?") in {
                            "goodbye",
                            "bye",
                            "end conversation",
                            "stop talking",
                        }:
                            self.emit(ConversationEvent(kind="goodbye"))
                    elif kind == "agent_response":
                        self.emit(ConversationEvent(kind="activity"))
                        self.emit(
                            ConversationEvent(kind="summary", detail="Agent response received")
                        )
                    elif kind == "error":
                        raise RuntimeError("ElevenLabs service reported an error")
            finally:
                if snapshot_task is not None:
                    snapshot_task.cancel()
                    await asyncio.gather(snapshot_task, return_exceptions=True)
