from phonybox.controller import Controller
from phonybox.hardware import Event
from phonybox.players.player import Player
from unittest.mock import Mock, MagicMock, AsyncMock
import contextlib
import asyncio
import pytest


@pytest.fixture
def controller():
    events = asyncio.Queue()
    controller = Controller(events)

    factory1 = Mock()
    factory1.wants.return_value = False
    factory1.return_value = MagicMock(spec=Player)
    factory2 = Mock()
    factory2.wants.return_value = True
    factory2.return_value = MagicMock(spec=Player)

    controller.factories = [ factory1, factory2 ]

    controller.current_player = MagicMock(spec=Player)
    return controller


@pytest.mark.asyncio
class TestController:
    @pytest.mark.parametrize("event_name", [ "play_pause", "next", "prev" ])
    async def test_command(self, controller, event_name, mocker):
        spy = mocker.spy(controller, f"on_{event_name}")

        task = asyncio.create_task(controller.run())
        try:
            controller.event_source.put_nowait(Event("control", event_name))
            await asyncio.sleep(0)
            spy.assert_awaited_once()
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


    @pytest.mark.parametrize("current_shuffle", [ True, False ])
    async def test_shuffle(self, controller, current_shuffle, mocker):
        player_shuffle = mocker.patch.object(controller.current_player, "shuffle", new_callable=AsyncMock, side_effect=lambda arg=None: current_shuffle if arg is None else None)

        task = asyncio.create_task(controller.run())
        try:
            controller.event_source.put_nowait(Event("control", "shuffle"))
            await asyncio.sleep(0)
            player_shuffle.assert_awaited_with(not current_shuffle)
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


    @pytest.mark.parametrize(("current_repeat", "next_repeat"), [ 
        (Player.RepeatType.NONE, Player.RepeatType.PLAYLIST),
        (Player.RepeatType.PLAYLIST, Player.RepeatType.TRACK),
        (Player.RepeatType.TRACK, Player.RepeatType.NONE)
    ])
    async def test_repeat(self, controller, current_repeat, next_repeat, mocker):
        player_repeat = mocker.patch.object(controller.current_player, "repeat", new_callable=AsyncMock, side_effect=lambda arg=None: current_repeat if arg is None else None)

        task = asyncio.create_task(controller.run())
        try:
            controller.event_source.put_nowait(Event("control", "repeat"))
            await asyncio.sleep(0)
            player_repeat.assert_awaited_with(next_repeat)
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


    async def test_card_wanted(self, controller, mocker):
        uri = "mock_player_uri"
        
        factory1, factory2 = controller.factories
        expected_player = factory2()
        factory2.reset_mock()

        task = asyncio.create_task(controller.run())
        try:
            controller.event_source.put_nowait(Event("nfc_tag", uri))
            await asyncio.sleep(0)
            assert controller.current_player is expected_player
            for factory in controller.factories:
                factory.wants.assert_called_once_with(uri)

            factory1.assert_not_called()
            factory2.assert_called_once()
            
            expected_player.play.assert_awaited_with(uri)
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


    async def test_card_none_want(self, controller, mocker):
        uri = "mock_player_uri"
        player_play = mocker.patch.object(controller.current_player, "play", new_callable=AsyncMock)

        task = asyncio.create_task(controller.run())
        try:
            controller.event_source.put_nowait(Event("nfc_tag", uri))
            await asyncio.sleep(0)
            player_play.assert_awaited_with(uri)
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task