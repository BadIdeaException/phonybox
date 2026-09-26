from typing import Self
from abc import ABC, abstractmethod
from enum import Enum

class Player(ABC):
    class RepeatType(Enum):
        NONE = 0
        TRACK = 1
        PLAYLIST = 2


    @abstractmethod
    async def play(self, uri: str) -> None:
        ...


    @abstractmethod
    async def pause(self) -> None:
        ...


    @abstractmethod
    async def next(self) -> None:
        ...


    @abstractmethod
    async def prev(self) -> None:
        ...


    @abstractmethod
    async def is_playing(self) -> bool:
        ...


    @abstractmethod
    async def shuffle(self, new_value: bool | None) -> bool:
        ...


    @abstractmethod
    async def repeat(self, new_value: RepeatType | None) -> RepeatType:
        ...