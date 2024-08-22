#
# This file is part of the linuxpy project
#
# Copyright (c) 2024 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

"""
Human friendly interface to linux LED subsystem.

```python
from linuxpy.led import find

caps_lock = find(function="capslock")
print(caps_lock.brightness)
caps_lock.brightness = caps_lock.max_brightness
```

### ULED

```python
from linuxpy.led import LED, ULED

with ULED("uled::simulation") as uled:
    led = LED.from_name("uled::simulation")
    print()
```

Streaming example:

```python
from time import monotonic

from linuxpy.led import ULED

with ULED("uled::simulation", max_brightness=100) as uled:
    # Open another terminal and type:
    # echo 10 > /sys/class/leds/uled::simulation/brightness
    for brightness in uled.stream():
        print(f"[{monotonic():.6f}]: {brightness}")
```
"""

import pathlib
import select
import struct

from linuxpy.device import BaseDevice
from linuxpy.sysfs import LED_PATH, Attr, Device, Int
from linuxpy.types import Callable, Iterable, Optional, Union
from linuxpy.util import make_find

# https://www.kernel.org/doc/html/latest/leds/leds-class.html


def decode_trigger(text):
    start = text.index("[")
    end = text.index("]")
    return text[start + 1 : end]


def decode_triggers(text):
    return [i[1:-1] if i.startswith("[") else i for i in text.split()]


def decode_brightness(data: bytes) -> int:
    return int.from_bytes(data, "little")


def split_name(fname):
    if nb_colons := fname.count(":"):
        parts = fname.split(":")
        return ("", *parts) if nb_colons == 1 else parts
    return "", "", fname


class LED(Device):
    """Main LED class"""

    _devicename = None
    _color = None
    _function = None

    brightness = Int()
    max_brightness = Int()
    trigger = Attr(decode=decode_trigger)
    triggers = Attr("trigger", decode=decode_triggers)

    def __repr__(self):
        klass_name = type(self).__name__
        return f"{klass_name}({self.name})"

    def _build_name(self):
        devicename, color, function = split_name(self.syspath.stem)
        self._devicename = devicename
        self._color = color
        self._function = function

    @classmethod
    def from_name(cls, name) -> "LED":
        """Create a LED from the name that corresponds /sys/class/leds/<name>"""
        return cls.from_syspath(LED_PATH / name)

    @property
    def name(self) -> str:
        """LED name from the naming <devicename:color:function>"""
        return self.syspath.stem

    @property
    def devicename(self) -> str:
        """LED device name from the naming <devicename:color:function>"""
        if self._devicename is None:
            self._build_name()
        return self._devicename

    @property
    def color(self) -> str:
        """LED color from the naming <devicename:color:function>"""
        if self._color is None:
            self._build_name()
        return self._color

    @property
    def function(self) -> str:
        """LED function from the naming <devicename:color:function>"""
        if self._function is None:
            self._build_name()
        return self._function

    @property
    def trigger_enabled(self) -> bool:
        """Tells if the LED trigger is enabled"""
        return self.trigger != "none"

    @property
    def brightness_events_path(self):
        return self.syspath / "brightness_hw_changed"

    def __iter__(self):
        if not self.brightness_events_path.exists():
            raise ValueError("This LED does not support hardware events")
        with self.brightness_events_path.open("rb", buffering=0) as fobj:
            yield decode_brightness(fobj.read(4))
            fobj.seek(0)


class ULED(BaseDevice):
    """
    LED class for th userspace LED. This can be useful for testing triggers and
    can also be used to implement virtual LEDs.
    """

    PATH = "/dev/uleds"

    def __init__(self, name: str, max_brightness: int = 1, **kwargs):
        self.name = name
        self.max_brightness = max_brightness
        self._brightness = None
        super().__init__(self.PATH, **kwargs)

    def _on_open(self):
        data = struct.pack("64si", self.name.encode(), self.max_brightness)
        self._fobj.write(data)
        self._brightness = self.brightness

    def read(self) -> bytes:
        """Read new brightness. Blocks until brightness changes"""
        if not self.is_blocking:
            select.select((self,), (), ())
        return self.raw_read()

    def raw_read(self) -> bytes:
        return self._fobj.read()

    @property
    def brightness(self) -> int:
        """Read new brightness. Blocks until brightness changes"""
        data = self.raw_read()
        if data is not None:
            self._brightness = decode_brightness(data)
        return self._brightness

    def stream(self) -> Iterable[int]:
        """Infinite stream of brightness change events"""
        while True:
            data = self.read()
            self._brightness = decode_brightness(data)
            yield self._brightness


def iter_device_paths() -> Iterable[pathlib.Path]:
    """Iterable of all LED syspaths (/sys/class/leds)"""
    yield from LED_PATH.iterdir()


def iter_devices() -> Iterable[LED]:
    """Iterable over all LED devices"""
    return (LED.from_syspath(path) for path in iter_device_paths())


_find = make_find(iter_devices, needs_open=False)


def find(find_all: bool = False, custom_match: Optional[Callable] = None, **kwargs) -> Union[LED, Iterable[LED], None]:
    """
    If find_all is False:

    Find a LED follwing the criteria matched by custom_match and kwargs.
    If no LED is found matching the criteria it returns None.
    Default is to return a random LED device.

    If find_all is True:

    The result is an iterator.
    Find all LEDs that match the criteria custom_match and kwargs.
    If no LED is found matching the criteria it returns an empty iterator.
    Default is to return an iterator over all LEDs found on the system.
    """
    return _find(find_all, custom_match, **kwargs)


def main():
    for dev in sorted(iter_devices(), key=lambda dev: dev.syspath.stem):
        print(f"{dev.syspath.stem:32} {dev.trigger:16} {dev.brightness:4}")


if __name__ == "__main__":
    main()
