from pathlib import Path
from typing import Literal
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All durations are seconds; motion coordinates are normalized, angles degrees."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", validate_assignment=True)
    app_mode: str = "development"
    motion_backend: Literal["simulation", "esp32"] = "simulation"
    conversation_backend: Literal["mock", "elevenlabs", "disabled"] = "mock"
    camera_index: int = Field(0, ge=0, le=20)
    camera_fps: int = Field(20, ge=5, le=60)
    camera_width: int = Field(1280, ge=320, le=1920)
    camera_height: int = Field(720, ge=240, le=1080)
    face_min_detection_confidence: float = Field(0.4, ge=0.2, le=0.9)
    face_min_presence_confidence: float = Field(0.4, ge=0.2, le=0.9)
    face_min_tracking_confidence: float = Field(0.4, ge=0.2, le=0.9)
    face_far_scan_enabled: bool = True
    face_far_scan_interval_seconds: float = Field(0.2, ge=0.1, le=1)
    face_model_path: Path = Path("assets/face_landmarker.task")
    face_detection_hold_seconds: float = Field(0.3, gt=0)
    face_facing_hold_seconds: float = Field(2, gt=0)
    face_dropout_seconds: float = Field(0.25, ge=0, le=1)
    face_yaw_threshold: float = Field(25, gt=0, le=90)
    face_pitch_threshold: float = Field(20, gt=0, le=90)
    neutral_yaw: float = 0
    neutral_pitch: float = 0
    eye_tracking_hz: float = Field(10, gt=0, le=60)
    eye_smoothing_seconds: float = Field(0.18, gt=0)
    eye_max_velocity: float = Field(2, gt=0)
    eye_max_pan_degrees: float = Field(20, gt=0, le=30)
    eye_max_tilt_degrees: float = Field(15, gt=0, le=25)
    conversation_idle_timeout_seconds: float = Field(30, gt=0)
    visitor_absence_timeout_seconds: float = Field(20, gt=0)
    max_session_duration_seconds: float = Field(180, gt=0)
    cooldown_rearm_absence_seconds: float = Field(5, gt=0)
    elevenlabs_agent_id: str = ""
    elevenlabs_api_key: SecretStr = SecretStr("")
    vision_context_enabled: bool = False
    vision_greeting_enabled: bool = True
    vision_context_interval_seconds: float = Field(6, ge=6, le=120)
    vision_context_timeout_seconds: float = Field(5, gt=0, le=10)
    vision_context_delivery_wait_seconds: float = Field(15, gt=0, le=30)
    vision_context_max_image_side: int = Field(640, ge=256, le=1280)
    serial_port: str = ""
    serial_baudrate: int = Field(115200, gt=0)
    debug_mode: bool = False
    audio_playback_buffer_ms: int = Field(120, ge=0, le=500)
    audio_playback_queue_seconds: float = Field(30, ge=15, le=60)
    audio_playback_max_wait_ms: int = Field(250, ge=20, le=1000)
    audio_input_chunk_ms: int = Field(100, ge=20, le=250)
    audio_suppress_mic_during_playback: bool = True
    ambience_enabled: bool = False
    ambience_fresh_effects_enabled: bool = False
    ambience_directory: Path = Path("assets/ambience_library")
    ambience_duration_seconds: float = Field(25, ge=20, le=30)
    ambience_volume: float = Field(0.15, ge=0, le=0.5)
    ambience_during_conversation: bool = True
    ambience_trigger_hold_seconds: float = Field(0.3, gt=0, le=3)
    ambience_rearm_seconds: float = Field(3, gt=0, le=30)
    ambience_cooldown_seconds: float = Field(10, ge=0, le=120)
    motion_pixel_threshold: int = Field(25, ge=5, le=100)
    motion_area_threshold: float = Field(0.015, gt=0, le=0.3)
    jaw_noise_gate: float = Field(0.015, ge=0, le=1)
    jaw_gain: float = Field(5, gt=0)
