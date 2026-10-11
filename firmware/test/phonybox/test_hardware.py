from phonybox.hardware import Hardware
from phonybox.drivers.pn532 import Card
from gpiozero import Button, LED, GPIODevice
import asyncio
import pytest
import pytest_asyncio
import time
from unittest.mock import Mock, patch


class MockPN532:    
    def __init__(self, irq_pin, *, forced_timeout=0.1, **kwargs):
        self.irq = GPIODevice(irq_pin)
        if forced_timeout is not None:
            self.forced_timeout = forced_timeout
        self._card = None


    def present_card(self, card: Card) -> None:
        self._card = card


    def remove_card(self):
        self._card = None
    

    def wait_for_card(self, timeout=1):
        t0 = time.monotonic()
        while time.monotonic() < t0 + (self.forced_timeout if self.forced_timeout is not None else timeout):
            if self._card is not None:                
                return bytes.fromhex(self._card.uid)


    def read_card(self, uid):
        return self._card


    def close(self):
        self.irq.close()


CONTROL_DEFINITION = [
        ("button_control", "button", 11),
        ("led_control", "led", 12),
        ("pn532_irq", "irq", 13)
    ]

@pytest_asyncio.fixture
async def hw():
    with patch("phonybox.hardware.PN532", MockPN532):
        return Hardware(CONTROL_DEFINITION)


@pytest.mark.asyncio
class TestCreateDevices:
    async def test_creates_controls(self, hw):
        with hw:
            for (name, kind, pin) in CONTROL_DEFINITION:
                if name == "pn532_irq":
                    continue
                assert name in hw.controls
                assert type(hw.controls[name]) == {
                        "button": Button, "led": LED
                    }[kind]
                assert hw.controls[name].pin.info.name == f"GPIO{pin}"


    async def test_unknown_control_kind(self):        
        with pytest.raises(ValueError):
            Hardware([("error_control", "unknown_kind", 5)])

    
    @pytest.mark.parametrize("control_name", ("button_control",))
    async def test_emits_events_on_control(self, hw, control_name):
        with hw:
            control = hw.controls[control_name]
            if control.pin.pull == "up":
                control.pin.drive_low()
                control.pin.drive_high()
            else:
                control.pin.drive_high()
                control.pin.drive_low()

            event = await asyncio.wait_for(hw.events.get(), timeout=0.1)
            assert event == control_name


    async def test_emits_events_on_card(self, hw):
        card = Card("01020304050607", object())
        with hw:
            hw.nfc.pn532.present_card(card)

            event = await asyncio.wait_for(hw.events.get(), timeout=0.1)
            hw.nfc.pn532.remove_card()

            assert isinstance(event, Card)
            assert event == card


    async def test_cleanup_on_context_manager_exit(self, hw):
        with hw:
            pass

        with pytest.raises(asyncio.QueueShutDown):
            hw.events.put_nowait(None)
        for control in hw.controls.values():
            assert control.closed
        assert hw.nfc.pn532.irq.closed
