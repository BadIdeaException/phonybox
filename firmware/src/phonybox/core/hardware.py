from __future__ import annotations
from gpiozero import Button, LED
import asyncio
import contextlib
import threading
import functools
from collections.abc import Callable, Iterable
from phonybox.drivers.pn532 import Card, PN532, NFCError
from typing import Coroutine, Literal
from dataclasses import dataclass
from .channel import Channel


type ControlDefinition = tuple[str, Literal["button", "led", "irq"], int]

type Control = Button | LED


@dataclass
class Event:
    type: str
    payload: str | Card

    @classmethod
    def from_payload(cls, payload: str | Card) -> Event:
        if isinstance(payload, Card):
            return Event("nfc_tag", payload)
        elif isinstance(payload, str):
            return Event("control", payload)        
        else:
            raise ValueError(f"Unknown payload kind {type(payload).__name__}")


class Hardware:
    controls: dict[str, Control]

    # Message channels
    outgoing: asyncio.Queue[Event]
    incoming: asyncio.Queue[Event]


    def __init__(self, controls: Iterable[ControlDefinition], *, outgoing: asyncio.Queue[Event]):
        self.controls = {}
        self.outgoing = outgoing
        try:
            irq_pin = None
            for (name, kind, pin) in controls:
                if kind == "button":                    
                    self.controls[name] = Button(pin)
                elif kind == "led":
                    self.controls[name] = LED(pin)
                elif kind == "irq":
                    irq_pin = pin
                else:
                    raise ValueError(f"Error creating {name} on pin {pin}: {kind} is not a recognized device type")

            self.pn532 = PN532(irq_pin=irq_pin)
        except:
            self.close()
            raise


    async def run(self, polling_timeout: int = 1) -> None:
        async def watch_button(name: str, button: Button):
            while True:
                await asyncio.to_thread(button.wait_for_press, timeout=polling_timeout)
                if button.is_pressed:
                    await self.outgoing.put(Event("control", name))

        async def watch_nfc():
            while True:
                uid = await asyncio.to_thread(self.pn532.wait_for_card, timeout=polling_timeout)
                if uid is not None:
                    card = await asyncio.to_thread(self.pn532.read_card, uid)
                    await self.outgoing.put(Event("nfc_tag", card))

        async with asyncio.TaskGroup() as tg:
            for name, control in self.controls.items():
                if isinstance(control, Button):
                    tg.create_task(watch_button(name, control))

            tg.create_task(watch_nfc())


    def close(self):
        self.outgoing.shutdown(immediate=True)
        for control in self.controls.values():
            if isinstance(control, LED):
                control.off()
            control.close()
        if hasattr(self, "pn532"):
            self.pn532.close()


    def __enter__(self):
        return self


    def __exit__(self, exctype, exc, tb):
        self.close()


    def __exit__(self, exctype, exc, tb):
        self.close()
