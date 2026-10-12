"""Validated agent requests for local visual effects; no hardware commands."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

PRESETS = ("calm", "inferno", "spectral", "storm", "hypnosis", "mischievous", "mirror")


class EyeCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preset: Literal["calm", "inferno", "spectral", "storm", "hypnosis", "mischievous", "mirror"]
    intensity: float = Field(0.9, ge=0, le=1)
    duration_seconds: float = Field(8, ge=2, le=20)
