from typing import override
from .player import Player
from websockets.asyncio.client import ClientConnection, connect
import json


class ProtocolError(RuntimeError):
    pass


class Spotify(Player):
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self._websocket = None


    async def _send_command(self, command: str, **kwargs):
        """
        Send a command over the websocket and check that the answer is ok.
        Any addition kwargs are sent as payload
        """

        # Open websocket if not already open
        if self._websocket is None:
            self._websocket = await connect(uri=f"ws://{self.host}:{self.port}")

        payload: dict = {
            "type": "command",
            "command": command,
            **kwargs
        }

        await self._websocket.send(json.dumps(payload))
        answer: dict = json.loads(await self._websocket.recv())
        if answer["type"] == "error":
            raise ProtocolError(answer["message"])
        elif not command.startswith("get") and answer["command"] != command:
            raise ProtocolError(f"Command mismatch: Spotify Soloist acknowledged receipt of {answer["command"]}, but we sent {command}")

        return answer


    @override 
    async def play(self, uri):
        await self._send_command("play", uri=uri)


    @override
    async def pause(self):
        await self._send_command("pause")


    @override
    async def next(self):
        await self._send_command("skip_next")


    @override
    async def prev(self):
        await self._send_command("skip_prev")


    @override
    async def shuffle(self, new_value = None):
        if new_value is not None:
            await self._send_command("set_shuffle", enabled=new_value)

        answer = await self._send_command("get_state")
        return answer["options"]["shuffle"]


    @override
    async def repeat(self, new_value = None):
        # See https://developer.spotify.com/documentation/soloist/reference/websocket-api
        if new_value is Player.RepeatType.NONE:
            await self._send_command("set_repeat_track", enabled=False)
            await self._send_command("set_repeat_context", enabled=False)
        elif new_value is Player.RepeatType.TRACK:
            await self._send_command("set_repeat_context", enabled=False)
            await self._send_command("set_repeat_track", enabled=True)
        elif new_value is Player.RepeatType.PLAYLIST:
            await self._send_command("set_repeat_track", enabled=False)
            await self._send_command("set_repeat_context", enabled=True)

        answer = await self._send_command("get_state")
        return {
            "off": Player.RepeatType.NONE,
            "track": Player.RepeatType.TRACK,
            "context": Player.RepeatType.PLAYLIST
        }[answer["options"]["repeat"]]
        
