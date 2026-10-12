"""Documented ElevenAgents WebSocket protocol, signed URL from official SDK.

Reference: https://elevenlabs.io/docs/agents-platform/libraries/web-sockets
Only recognized documented events are consumed; no transcript is persisted.
"""

import asyncio
import base64
import json
import random
from malachi.events import ConversationEvent


class ElevenLabsServiceError(RuntimeError):
    def __init__(self, message):
        super().__init__("ElevenLabs service reported an error")
        # Only extract structured error text through the shared redaction helper.
        event = message.get("error_event", message)
        self.body = {"detail": event} if isinstance(event, dict) else {}


class ElevenLabsClient:
    def __init__(self, settings, playback, audio, emit, image_uploader=None):
        self.settings, self.playback, self.audio, self.emit = settings, playback, audio, emit
        self.snapshot = None
        self.snapshot_provider = None
        self.image_upload_disabled = False
        self.image_uploader = image_uploader
        self.last_audio_received = None
        self.connected_at = None
        self.greeting_pending = False
        self.opening_style = None
        self.response_pending_until = 0.0
        self.audio_overflow_reported = False
        self.last_eye_command = float("-inf")
        self.last_lighting_command = float("-inf")

    async def _deliver_snapshot(self, ws, conversation_id, stop):
        from malachi.vision.scene_context import ElevenLabsImageUploader, PHOTO_INSTRUCTIONS
        from elevenlabs.conversational_ai.conversation import (
            MultimodalMessageClientToOrchestratorEvent,
        )

        jpeg = self.snapshot.take() if self.snapshot is not None else None
        self.snapshot = None
        if not jpeg or stop.is_set():
            if self.greeting_pending and not stop.is_set():
                await self._fallback_greeting(ws, stop)
            return
        try:
            self.emit(
                ConversationEvent(kind="scene", detail="Uploading camera snapshot to ElevenLabs")
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
                if self.image_upload_disabled:
                    return
                now = loop.time()
                pending = (
                    self.playback.samples > 0
                    or self.audio.agent_speaking
                    or self.audio.user_speaking
                    or now < self.response_pending_until
                )
                if self.last_audio_received is None:
                    settling = self.connected_at is not None and now - self.connected_at < 1.0
                else:
                    settling = now - self.last_audio_received < 0.35
                if not pending and not settling:
                    text = PHOTO_INSTRUCTIONS
                    if self.greeting_pending:
                        from malachi.vision.scene_context import opening_instruction

                        text += "\n\n" + opening_instruction(self.opening_style)
                    message = MultimodalMessageClientToOrchestratorEvent(
                        text=text, file_ids=[file_id]
                    ).to_dict()
                    self.response_pending_until = loop.time() + 15
                    await asyncio.wait_for(ws.send(json.dumps(message)), timeout=2)
                    self.greeting_pending = False
                    self.audio.opening_pending = False
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
        except asyncio.CancelledError:
            self.greeting_pending = False
            raise
        except asyncio.TimeoutError:
            self.emit(
                ConversationEvent(
                    kind="scene", detail="Image upload/delivery timed out; voice continues"
                )
            )
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            # Unsupported configuration/authentication will not improve this session.
            if status in (400, 401, 403, 429):
                self.image_upload_disabled = True
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
            if self.greeting_pending and not stop.is_set():
                await self._fallback_greeting(ws, stop)

    async def _fallback_greeting(self, ws, stop):
        from malachi.vision.scene_context import opening_instruction

        if stop.is_set():
            return
        self.greeting_pending = False
        self.audio.opening_pending = False
        self.response_pending_until = asyncio.get_running_loop().time() + 15
        try:
            await asyncio.wait_for(
                ws.send(
                    json.dumps(
                        {
                            "type": "user_message",
                            "text": opening_instruction(self.opening_style, has_image=False),
                        }
                    )
                ),
                timeout=2,
            )
            self.emit(
                ConversationEvent(
                    kind="scene", detail="Visual opening unavailable; requested nonvisual greeting"
                )
            )
        except Exception:
            self.emit(
                ConversationEvent(
                    kind="scene", detail="Opening delivery failed; voice input remains available"
                )
            )

    async def _snapshot_loop(self, ws, conversation_id, stop):
        from malachi.vision.scene_context import PreparedSnapshot, encode_snapshot

        while not stop.is_set():
            await self._deliver_snapshot(ws, conversation_id, stop)
            if self.snapshot_provider is None or self.image_upload_disabled:
                return
            # One task, no queued frames and no catch-up burst after slow delivery.
            await asyncio.sleep(self.settings.vision_context_interval_seconds)
            if stop.is_set():
                return
            try:
                frame = await asyncio.to_thread(self.snapshot_provider)
                if frame is not None:
                    jpeg = await asyncio.to_thread(
                        encode_snapshot, frame, self.settings.vision_context_max_image_side
                    )
                    self.snapshot = PreparedSnapshot(jpeg)
                    jpeg = None
                frame = None
            except Exception as exc:
                self.emit(
                    ConversationEvent(
                        kind="scene",
                        detail=f"Snapshot skipped ({type(exc).__name__}); voice continues",
                    )
                )

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
        visual_opening = False
        override_first_message = False
        if self.settings.vision_context_enabled and self.settings.vision_greeting_enabled:
            from malachi.diagnostics import check_agent

            try:
                config = await asyncio.to_thread(check_agent, self.settings)
                override_first_message = config["first_message_override_allowed"]
                visual_opening = override_first_message or config["first_message_empty"]
            except Exception as exc:
                self.emit(
                    ConversationEvent(
                        kind="scene",
                        detail=f"Visual greeting configuration unavailable ({type(exc).__name__}); retaining agent greeting",
                    )
                )
            if not visual_opening:
                self.emit(
                    ConversationEvent(
                        kind="scene",
                        detail="Visual greeting disabled: enable First message overrides or clear the agent First message; voice continues",
                    )
                )
        if stop.is_set():
            return
        async with connect(signed.signed_url, open_timeout=10, max_size=16 * 1024 * 1024) as ws:
            # Always supply a fallback so an agent prompt using {{visual_context}}
            # still works when analysis is disabled, unavailable or timed out.
            initiation = {
                "type": "conversation_initiation_client_data",
                "dynamic_variables": {
                    "visual_context": "Camera images may arrive as attachments during this conversation. "
                    "Use the attached image once received; this placeholder is not a scene description. "
                    "Do not invent details if no image is available."
                },
            }
            if visual_opening:
                from malachi.vision.scene_context import OPENING_STYLES

                self.greeting_pending = True
                self.opening_style = self.opening_style or random.choice(OPENING_STYLES)
                if override_first_message:
                    initiation["conversation_config_override"] = {"agent": {"first_message": ""}}
            await ws.send(json.dumps(initiation))
            loop = asyncio.get_running_loop()

            def send(audio):
                future = asyncio.run_coroutine_threadsafe(
                    ws.send(json.dumps({"user_audio_chunk": base64.b64encode(audio).decode()})),
                    loop,
                )
                try:
                    future.result(timeout=2)
                except Exception:
                    future.cancel()
                    raise

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
                        self.audio.opening_pending = self.greeting_pending
                        await asyncio.to_thread(self.audio.start, send)
                        ready = True
                        self.connected_at = loop.time()
                        self.emit(ConversationEvent(kind="connected"))
                        if (
                            self.snapshot is not None
                            or self.snapshot_provider is not None
                            or self.greeting_pending
                        ):
                            snapshot_task = asyncio.create_task(
                                self._snapshot_loop(ws, meta["conversation_id"], stop)
                            )
                    elif kind == "audio":
                        if not ready:
                            raise ValueError("Audio received before session metadata")
                        if int(message["audio_event"]["event_id"]) <= last_interrupt_id:
                            continue
                        self.last_audio_received = loop.time()
                        self.response_pending_until = 0.0
                        dropped = self.playback.push(
                            base64.b64decode(message["audio_event"]["audio_base_64"])
                        )
                        if dropped:
                            self.image_upload_disabled = True
                            if not self.audio_overflow_reported:
                                self.audio_overflow_reported = True
                                self.emit(
                                    ConversationEvent(
                                        kind="summary",
                                        detail="Speech backlog limit reached: excess audio skipped; image updates disabled for this session; voice continues",
                                    )
                                )
                        self.emit(ConversationEvent(kind="activity"))
                    elif kind == "interruption":
                        self.response_pending_until = 0.0
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
                        self.response_pending_until = loop.time() + 15
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
                        self.response_pending_until = loop.time() + 5
                        self.emit(ConversationEvent(kind="activity"))
                        self.emit(
                            ConversationEvent(kind="summary", detail="Agent response received")
                        )
                    elif kind == "client_tool_call":
                        from malachi.ui.eye_commands import EyeCommand, LightingCommand

                        call = message.get("client_tool_call", {})
                        result = {
                            "type": "client_tool_result",
                            "tool_call_id": call.get("tool_call_id"),
                            "is_error": False,
                        }
                        try:
                            name = call.get("tool_name")
                            if name == "set_eye_effect":
                                if loop.time() - self.last_eye_command < 1:
                                    raise ValueError("Too many eye changes")
                                command = EyeCommand.model_validate(call.get("parameters", {}))
                                kind, label = "eye_effect", command.preset
                                self.last_eye_command = loop.time()
                            elif name == "set_underlighting":
                                if loop.time() - self.last_lighting_command < 1:
                                    raise ValueError("Too many lighting changes")
                                command = LightingCommand.model_validate(call.get("parameters", {}))
                                kind, label = "lighting_effect", command.color
                                self.last_lighting_command = loop.time()
                            else:
                                raise ValueError("Unknown tool")
                            self.emit(
                                ConversationEvent(kind=kind, detail=command.model_dump_json())
                            )
                            result["result"] = (
                                f"Queued {kind}: {label} for {command.duration_seconds:g} seconds"
                            )
                        except Exception:
                            result["is_error"] = True
                            result["result"] = (
                                "Unsupported tool or invalid parameters; use listed preset/color/effect values, intensity/brightness 0-1, duration 2-20 seconds, at most one change per tool per second."
                            )
                        await ws.send(json.dumps(result))
                    elif kind == "error":
                        raise ElevenLabsServiceError(message)
            finally:
                # Stop microphone sends before the socket context closes. Audio
                # streams are closed by the manager after this coroutine returns.
                audio_stop = getattr(self.audio, "stop_event", None)
                if audio_stop is not None:
                    audio_stop.set()
                self.audio.opening_pending = False
                if snapshot_task is not None:
                    snapshot_task.cancel()
                    await asyncio.gather(snapshot_task, return_exceptions=True)
                if self.snapshot is not None:
                    self.snapshot.take()
                    self.snapshot = None
