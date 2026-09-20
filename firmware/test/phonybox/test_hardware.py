from phonybox.hardware import Hardware
from gpiozero import Button, LED, DigitalInputDevice
import pytest
import asyncio

CONTROL_DEFINITION = [
        ("button_control", "button", 11),
        ("led_control", "led", 12),
        ("irq_control", "input", 13),
    ]

@pytest.fixture
def hw():
    return Hardware(CONTROL_DEFINITION)


class TestCreateDevices:
    def test_creates_controls(self, hw):
        with hw:
            for (name, kind, pin) in CONTROL_DEFINITION:
                assert name in hw.controls
                assert type(hw.controls[name]) == {
                        "button": Button, "led": LED, "input": DigitalInputDevice
                    }[kind]
                assert hw.controls[name].pin.info.name == f"GPIO{pin}"


    def test_unknown_control_kind(self):
        with pytest.raises(ValueError):
            Hardware([("error_control", "unknown_kind", 5)])

    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("control_name", ("button_control", "irq_control"))
    async def test_emits_events(self, hw, control_name):
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


    def test_cleanup_on_context_manager_exit(self, hw):
        with hw:
            pass

        with pytest.raises(asyncio.QueueShutDown):
            hw.events.put_nowait(None)
        for control in hw.controls.values():
            assert control.closed