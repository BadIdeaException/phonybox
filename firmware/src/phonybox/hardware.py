from gpiozero import Button, LED, DigitalInputDevice
from asyncio import Queue

type Control = Button | LED | DigitalInputDevice

class Hardware:
    controls: dict[str, Control]
    events: Queue


    def __init__(self, controls):
        self.controls = {}
        self.events = Queue()
        try:
            for (name, kind, pin) in controls:
                if kind == "button":
                    control = Button(pin)
                    control.when_pressed = lambda name=name: self.events.put_nowait(name)
                    self.controls[name] = control
                elif kind == "led":
                    self.controls[name] = LED(pin)
                elif kind == "input":
                    control = DigitalInputDevice(pin)
                    control.when_activated = lambda name=name: self.events.put_nowait(name)
                    self.controls[name] = control
                else:
                    raise ValueError(f"Error creating {name} on pin {pin}: {kind} is not a recognized device type")
        except:
            self._close()
            raise


    def _close(self):
        self.events.shutdown(immediate=True) # discard pending events in queue
        for control in self.controls.values():
            if isinstance(control, LED):
                control.off()
            control.close()


    def __enter__(self):
        return self


    def __exit__(self, exctype, exc, tb):
        self._close()