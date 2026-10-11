import json
from typing import Literal, Union, Annotated
from pydantic import BaseModel, Field, ConfigDict, TypeAdapter


class BaseCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    v: Literal[1] = 1
    seq: int = Field(ge=0, le=2147483647)


class Eyes(BaseCommand):
    type: Literal["EYES"]
    x: float = Field(ge=-1, le=1)
    y: float = Field(ge=-1, le=1)


class Jaw(BaseCommand):
    type: Literal["JAW"]
    open: float = Field(ge=0, le=1)


class Head(BaseCommand):
    type: Literal["HEAD"]
    pan: float = Field(ge=-1, le=1)
    tilt: float = Field(ge=-1, le=1)


class Led(BaseCommand):
    type: Literal["LED"]
    effect: Literal["off", "red_pulse", "purple_glow"]


class Stop(BaseCommand):
    type: Literal["STOP", "RESET", "PING"]


COMMAND = TypeAdapter(Annotated[Union[Eyes, Jaw, Head, Led, Stop], Field(discriminator="type")])
MAX_PACKET = 256


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def encode(data):
    command = COMMAND.validate_python(data)
    packet = (command.model_dump_json() + "\n").encode()
    if len(packet) > MAX_PACKET:
        raise ValueError("packet too large")
    return packet


class Framer:
    def __init__(self):
        self.buffer = bytearray()
        self.discard = False

    def feed(self, data):
        packets = []
        for byte in data:
            if byte == 10:
                if not self.discard and self.buffer:
                    raw = bytes(self.buffer)
                    self.buffer.clear()
                    packets.append(
                        COMMAND.validate_python(json.loads(raw, object_pairs_hook=unique_keys))
                    )
                self.buffer.clear()
                self.discard = False
            elif not self.discard:
                self.buffer.append(byte)
                if len(self.buffer) >= MAX_PACKET:
                    self.buffer.clear()
                    self.discard = True
        return packets


def parse_reply(line):
    if len(line) > MAX_PACKET:
        raise ValueError("oversize reply")
    value = json.loads(line)
    if (
        not isinstance(value, dict)
        or value.get("v") != 1
        or value.get("type") not in ("ACK", "ERROR")
        or type(value.get("seq")) is not int
    ):
        raise ValueError("invalid acknowledgment")
    return value
