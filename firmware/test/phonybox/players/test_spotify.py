import pytest
from phonybox.players.spotify import Spotify, ProtocolError
import websockets.asyncio.server as websockets
import json
import re


# Simple Websocket handler that just stores all received messages and
# answers them with pre-defined responses
class Handler:    
    def __init__(self, *, responses = []):
        self.received = []
        self.responses = responses


    async def handle(self, connection: websockets.ServerConnection):
            async for message in connection:
                answer = self.responses[len(self.received)]
                self.received.append(json.loads(message))
                await connection.send(json.dumps(answer))


@pytest.fixture
def spotify():
    return Spotify("127.0.0.1", 10000)


class TestSpotify:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("command", "spotify_command", "extras"),
        [
            ("play", "play", { "uri": "spotify:track:123"} ),
            ("pause", "pause", {}),
            ("next", "skip_next", {}),
            ("prev", "skip_prev", {})
        ], 
        ids=[ "play", "pause", "next", "prev" ])
    async def test_command(self, spotify, command, spotify_command, extras):
        handler = Handler(responses = [{
            "type": "command_result",
            "command": spotify_command
        }])

        async with websockets.serve(handler.handle, host="127.0.0.1", port=spotify.port):
            method = getattr(spotify, command)
            await method(**extras)
            
            assert handler.received == [
                { "type": "command", "command": spotify_command, **extras }
            ]


    @pytest.mark.asyncio
    async def test_error(self, spotify):
        message = "Error message"
        handler = Handler(responses = [
            { "type": "error", "message": message }
        ])

        async with websockets.serve(handler.handle, host="127.0.0.1", port=spotify.port):
            with pytest.raises(ProtocolError, match=message):
                await spotify.pause()
            

    @pytest.mark.asyncio
    async def test_command_mismatch(self, spotify):
        handler = Handler(responses = [
            { "type": "command_result", "command": "play" }
        ])

        async with websockets.serve(handler.handle, host="127.0.0.1", port=spotify.port):
            with pytest.raises(ProtocolError, match=re.compile("command mismatch", re.I)):
                await spotify.pause()


    @pytest.mark.asyncio
    async def test_get_shuffle(self, spotify):
        handler = Handler(responses = [
            { "type": "playback_state", "options": { "shuffle": False }}
        ])

        async with websockets.serve(handler.handle, host="127.0.0.1", port=spotify.port):
            result = await spotify.shuffle()
            assert result == False


    @pytest.mark.asyncio
    async def test_set_shuffle(self, spotify):
        handler = Handler(responses = [
            { "type": "command_result", "command": "set_shuffle" },
            { "type": "playback_state", "options": { "shuffle": False }}
        ])

        async with websockets.serve(handler.handle, host="127.0.0.1", port=spotify.port):
            await spotify.shuffle(False)
            assert handler.received[0] == { "type": "command", "command": "set_shuffle", "enabled": False }        


    @pytest.mark.asyncio
    @pytest.mark.parametrize(("spotify_repeat", "repeat"), [ 
        ("off", Spotify.RepeatType.NONE), 
        ("track", Spotify.RepeatType.TRACK),
        ("context", Spotify.RepeatType.PLAYLIST)
    ], ids=[ "Spotify.RepeatType.NONE", "Spotify.RepeatType.TRACK", "Spotify.RepeatType.PLAYLIST"])
    async def test_get_repeat(self, spotify, spotify_repeat, repeat):
        handler = Handler(responses = [
            { "type": "playback_state", "options": { "repeat": spotify_repeat }}
        ])

        async with websockets.serve(handler.handle, host="127.0.0.1", port=spotify.port):
            result = await spotify.repeat()
            assert result is repeat


    @pytest.mark.asyncio
    @pytest.mark.parametrize(("repeat", "sequence"), [ 
        (Spotify.RepeatType.NONE, [{ "kind": "track", "value": False }, { "kind": "context", "value": False }] ),
        (Spotify.RepeatType.TRACK, [{ "kind": "context", "value": False }, { "kind": "track", "value": True }] ),
        (Spotify.RepeatType.PLAYLIST, [{ "kind": "track", "value": False }, { "kind": "context", "value": True }]),
    ], ids=[ "Spotify.RepeatType.NONE", "Spotify.RepeatType.TRACK", "Spotify.RepeatType.PLAYLIST"])
    async def test_set_repeat(self, spotify, repeat, sequence):
        handler = Handler(responses = [
            { "type": "command_result", "command": f"set_repeat_{item["kind"]}", "enabled": item["value"] } for item in sequence
        ] + [ 
            { "type": "playback_state", "options": { "repeat": ["off","track","context"][repeat.value] }}
        ])
        async with websockets.serve(handler.handle, host="127.0.0.1", port=spotify.port):
            await spotify.repeat(repeat)
            assert handler.received[0:2] == [
                { "type": "command", "command": f"set_repeat_{item["kind"]}", "enabled": item["value"] } for item in sequence
            ]


    @pytest.mark.asyncio
    async def test_is_playing(self, spotify):
        handler = Handler(responses = [
            # See https://developer.spotify.com/documentation/soloist/reference/websocket-api
            { "type": "playback_state", "status": "playing" },
            { "type": "playback_state", "status": "buffering" },
            { "type": "playback_state", "status": "paused" },
            { "type": "playback_state", "status": "idle" }
        ])

        async with websockets.serve(handler.handle, host="127.0.0.1", port=spotify.port):
            assert await spotify.is_playing()
            assert await spotify.is_playing()
            assert not await spotify.is_playing()
            assert not await spotify.is_playing()