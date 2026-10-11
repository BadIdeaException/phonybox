from abc import ABC, abstractmethod
from .card import Card
import ndef


class Reader(ABC):
    def __init__(self, uid: bytes):
        self.uid = uid


    @abstractmethod
    def read_ndef_raw(self) -> bytes:
        ...


    def read_ndef(self) -> ndef.Record:
        ndef_raw = self.read_ndef_raw()
        with ndef.message_decoder(ndef_raw) as decoder:
            return next(decoder)
