from phonybox.core.hardware import Hardware, StatusEvent
from phonybox.drivers.pn532 import Card
from gpiozero import Button, LED, GPIODevice
import asyncio
import contextlib
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
        ("button_control", "button", 10),
        ("led1_control", "led", 11),
        ("led2_control", "led", 12),
        ("pn532_irq", "irq", 13)
    ]


@pytest.fixture(autouse=True)
def mock_pn532(monkeypatch):
    monkeypatch.setattr("phonybox.core.hardware.PN532", MockPN532)


@pytest_asyncio.fixture
async def hw():
    return Hardware(CONTROL_DEFINITION, outgoing=asyncio.Queue(), incoming=asyncio.Queue())


@pytest.mark.asyncio
class TestHardware:
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
            Hardware([("error_control", "unknown_kind", 5)], outgoing=asyncio.Queue(), incoming=asyncio.Queue())

    
    @pytest.mark.parametrize("control_name", ("button_control",))
    async def test_emits_events_on_control(self, hw, control_name):
        with hw:
            run_task = asyncio.create_task(hw.run(polling_timeout=0.1))
            control = hw.controls[control_name]
            if control.pin.pull == "up":
                control.pin.drive_low()
                release = control.pin.drive_high
            else:
                control.pin.drive_high()
                release = control.pin.drive_low

            try:
                event = await asyncio.wait_for(hw.outgoing.get(), timeout=0.1)
                assert event.type == "control"
                assert event.payload == control_name
            finally:
                release()
                run_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await run_task


    async def test_emits_events_on_card(self, hw):
        card = Card("01020304050607", object())
        with hw:
            run_task = asyncio.create_task(hw.run(polling_timeout=0.1))
            hw.pn532.present_card(card)

            try:
                event = await asyncio.wait_for(hw.outgoing.get(), timeout=0.1)
                assert event.type == "nfc_tag"
                assert isinstance(event.payload, Card)
                assert event.payload == card
            finally:
                hw.pn532.remove_card()
                run_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await run_task


    async def test_cleanup_on_context_manager_exit(self, hw):
        with hw:
            pass

        with pytest.raises(asyncio.QueueShutDown):
            hw.outgoing.put_nowait(None)
        for control in hw.controls.values():
            assert control.closed
        assert hw.pn532.irq.closed


    @pytest.mark.parametrize("status", [ 
        pytest.param({ "led1_control": 1 }, id="simple on"),
        pytest.param({ "led1_control": 0 }, id="simple off"),
        pytest.param({ "led1_control": 0, "led2_control": 0 }, id="complex both off"),
        pytest.param({ "led1_control": 1, "led2_control": 1 }, id="complex both on"),
        pytest.param({ "led1_control": 0, "led2_control": 1 }, id="complex mixed")
    ])
    async def test_receives_status(self, hw, status):
        with hw:
            run_task = asyncio.create_task(hw.run(polling_timeout=0.01))
            
            try:
                for control_name, value in status.items():
                    hw.controls[control_name].value = int(not value)
                    hw.incoming.put_nowait(StatusEvent("status", status))
                    await asyncio.sleep(0.01)
                    assert hw.controls[control_name].value == value
            finally:
                run_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await run_task

