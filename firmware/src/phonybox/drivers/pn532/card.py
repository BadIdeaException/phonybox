from dataclasses import dataclass
import ndef


@dataclass
class Card:
    uid: str
    ndef: ndef.Record
