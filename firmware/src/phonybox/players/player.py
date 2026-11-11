from typing import Self, Protocol
from abc import ABC, abstractmethod
from enum import IntEnum


class PlayerFactory(Protocol):
    @classmethod
    def wants(cls, uri) -> bool:
        ...

    def __call__(self) -> Player: 
        ...


class Player(ABC, PlayerFactory):
    class RepeatType(IntEnum):
        NONE = 0
        PLAYLIST = 1
        TRACK = 2


    @abstractmethod
    async def play(self, uri: None | str = None) -> None:
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
    async def shuffle(self, new_value: bool | None = None) -> bool:
        ...


    @abstractmethod
    async def repeat(self, new_value: RepeatType | None = None) -> RepeatType:
        ...
