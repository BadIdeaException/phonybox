from gpiozero import Device
from gpiozero.pins.mock import MockFactory


Device.pin_factory = MockFactory()
