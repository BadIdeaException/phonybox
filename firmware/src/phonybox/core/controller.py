from phonybox.players.player import Player, PlayerFactory
from .hardware import StatusIndicator
import asyncio


class Controller:    
    current_player: Player | None
    events: asyncio.Queue
    factories: list[PlayerFactory]

    
    def __init__(self, event_source, status_indicator: StatusIndicator):
        self.current_player = None
        self.event_source = event_source
        self.status_indicator = status_indicator
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
        self.status_indicator.show_status("shuffle", shuffle)


    async def on_repeat(self) -> None:
        assert self.current_player is not None
        repeat = await self.current_player.repeat()
        repeat = await self.current_player.repeat(Player.RepeatType((repeat + 1) % 3))
        self.status_indicator.show_status("repeat", repeat)


    async def run(self) -> None:
        while True:
            event = await self.event_source.get()
            if event.type == "nfc_tag":
                uri = event.payload                
                player_factory = next(player for player in self.factories if player.wants(uri))
                self.current_player = player_factory()
                await self.current_player.play(uri)
            if self.current_player is None:
                continue

            if event.type == "control":
                await getattr(self, f"on_{event.payload}")()
