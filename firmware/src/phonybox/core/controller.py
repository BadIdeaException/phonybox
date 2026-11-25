from phonybox.players.player import Player, PlayerFactory
from .message import Message, StatusMessage
import asyncio


class Controller:    
    current_player: Player | None
    factories: list[PlayerFactory]
    incoming: asyncio.Queue[Message]
    outgoing: asyncio.Queue[Message]

    
    STATUS_SHUFFLE_ON = { "shuffle": 1 }
    STATUS_SHUFFLE_OFF = { "shuffle": 0 }
    STATUS_REPEAT_NONE = { "repeat_track": 0, "repeat_playlist": 0 }
    STATUS_REPEAT_PLAYLIST = { "repeat_track": 0, "repeat_playlist": 1 }
    STATUS_REPEAT_TRACK = { "repeat_track": 1, "repeat_playlist": 0 }


    def __init__(self, incoming: asyncio.Queue[Message], outgoing: asyncio.Queue[Message]):
        self.current_player = None
        self.incoming = incoming
        self.outgoing = outgoing
        self.factories = []


    async def on_play_pause(self) -> None:
        assert self.current_player is not None
        if await self.current_player.is_playing():
            await self.current_player.pause()
        else:
            await self.current_player.play()


    async def on_next(self) -> None:
        assert self.current_player is not None
        await self.current_player.next()


    async def on_prev(self) -> None:
        assert self.current_player is not None
        await self.current_player.prev()


    async def on_shuffle(self) -> None:
        assert self.current_player is not None
        shuffle = await self.current_player.shuffle()
        shuffle = await self.current_player.shuffle(not shuffle)
        status = getattr(Controller, f"STATUS_SHUFFLE_{"ON" if shuffle else "OFF"}")
        self.outgoing.put_nowait(StatusMessage(status))


    async def on_repeat(self) -> None:
        assert self.current_player is not None
        repeat = await self.current_player.repeat()
        repeat = await self.current_player.repeat(Player.RepeatType((repeat + 1) % 3))
        status = getattr(Controller, f"STATUS_REPEAT_{repeat.name.upper()}")
        self.outgoing.put_nowait(StatusMessage(status))


    async def run(self) -> None:
        while True:
            event = await self.incoming.get()
            if event.type == "nfc_tag":
                uri = event.payload                
                player_factory = next(player for player in self.factories if player.wants(uri))
                self.current_player = player_factory()
                await self.current_player.play(uri)
            if self.current_player is None:
                continue

            if event.type == "control":
                await getattr(self, f"on_{event.payload}")()
