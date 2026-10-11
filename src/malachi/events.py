from typing import Literal
from pydantic import BaseModel, Field


class Face(BaseModel):
    track_id: int
    center_x: float = Field(ge=0, le=1)
    center_y: float = Field(ge=0, le=1)
    box: tuple[float, float, float, float]
    yaw: float
    pitch: float
    confidence: float = Field(ge=0, le=1)
    stable: bool = False


class ConversationEvent(BaseModel):
    kind: Literal[
        "connected",
        "closed",
        "error",
        "activity",
        "user_start",
        "user_end",
        "agent_start",
        "agent_end",
        "goodbye",
        "summary",
    ]
    detail: str = ""
