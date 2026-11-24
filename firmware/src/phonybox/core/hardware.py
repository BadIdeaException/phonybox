from __future__ import annotations
from gpiozero import Button, LED
import asyncio
import contextlib
from threading import Thread
from collections.abc import Callable, Iterable
from phonybox.drivers.pn532 import Card, PN532, NFCError
from typing import override
from dataclasses import dataclass


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
    events: asyncio.Queue


    class NFC_Thread(Thread):
        when_card: Callable[[Card], None] | None = None

        def __init__(self, irq_pin: int | None = None):
            self.pn532 = PN532(irq_pin)
            self._closed = False
            super().__init__(daemon=True)


        @override
        def run(self):
            while True:
                uid = self.pn532.wait_for_card(timeout=1)
                if self._closed: 
                    break
                if uid is None: 
                    continue
                try:
                    card = self.pn532.read_card(uid)
                except NFCError:
                    continue

                if card is not None and self.when_card is not None:
                    self.when_card(card)


        def close(self):
            self._closed = True
            self.pn532.close()


    def __init__(self, controls: Iterable[tuple[str, str, int]]):
        loop = asyncio.get_running_loop()
        def put_event(event: str | Card) -> None:
            """
            Enqueue the given event if the queue is still active. Thread-safe.
            """
            def enqueue_if_possible(event: Event):
                with contextlib.suppress(asyncio.QueueShutDown): 
                    self.events.put_nowait(event)

            loop.call_soon_threadsafe(enqueue_if_possible, Event.from_payload(event))

        self.controls = {}
        self.events = asyncio.Queue()
        self.nfc = None
        try:
            irq_pin = None
            for (name, kind, pin) in controls:
                if kind == "button":
                    control = Button(pin)
                    control.when_pressed = lambda name=name: put_event(name)
                    self.controls[name] = control
                elif kind == "led":
                    self.controls[name] = LED(pin)
                elif kind == "irq":
                    irq_pin = pin
                else:
                    raise ValueError(f"Error creating {name} on pin {pin}: {kind} is not a recognized device type")

            self.nfc = Hardware.NFC_Thread(irq_pin)
            self.nfc.when_card = put_event
            self.nfc.start()
        except:
            self.close()
            raise


    def close(self):
        self.events.shutdown(immediate=True) # discard pending events in queue
        for control in self.controls.values():
            if isinstance(control, LED):
                control.off()
            control.close()
        if self.nfc is not None:
            self.nfc.close()


    def __enter__(self):
        return self


    def __exit__(self, exctype, exc, tb):
        self.close()