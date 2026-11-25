from typing import Literal
from dataclasses import dataclass
from phonybox.drivers.pn532.card import Card


@dataclass
class ControlMessage:
    type: Literal["control"]
    payload: str
    def __init__(self, payload: str):
        self.type = "control"
        self.payload = payload


@dataclass
class NFCMessage:
    type: Literal["nfc_tag"]
    payload: Card
    def __init__(self, payload: Card):
        self.type = "nfc_tag"
        self.payload = payload

@dataclass
class StatusMessage:
    type: Literal["status"]
    payload: dict[str, int]
    def __init__(self, payload: dict[str, int]):
        self.type = "status"
        self.payload = payload

type Message = ControlMessage | NFCMessage | StatusMessage