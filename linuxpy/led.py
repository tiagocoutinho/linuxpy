#
# This file is part of the linuxpy project
#
# Copyright (c) 2024 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import pathlib
import select
import struct

from linuxpy.device import BaseDevice
from linuxpy.sysfs import LED_PATH, Attr, Device, Int
from linuxpy.types import Iterable

# https://www.kernel.org/doc/html/latest/leds/leds-class.html


def decode_trigger(text):
    start = text.index("[")
    end = text.index("]")
    return text[start + 1 : end]


def decode_triggers(text):
    return [i[1:-1] if i.startswith("[") else i for i in text.split()]


class LED(Device):
    _devicename = None
    _color = None
    _function = None

    brightness = Int()
    max_brightness = Int()
    trigger = Attr(decode=decode_trigger)
    triggers = Attr("trigger", decode=decode_triggers)

    def _build_name(self):
        fname = self.syspath.stem
        if ":" in fname:
            if fname.count(":") == 1:
                devicename = ""
                color, function = fname.split(":")
            else:
                devicename, color, function = fname.split(":")
        else:
            devicename, color, function = "", "", fname
        self._devicename = devicename
        self._color = color
        self._function = function

    @classmethod
    def from_name(cls, n):
        return cls.from_syspath(LED_PATH / n)

    @property
    def devicename(self):
        if self._devicename is None:
            self._build_name()
        return self._devicename

    @property
    def color(self):
        if self._color is None:
            self._build_name()
        return self._color

    @property
    def function(self):
        if self._function is None:
            self._build_name()
        return self._function

    @property
    def trigger_enabled(self):
        return self.trigger != "none"


class ULED(BaseDevice):
    PATH = "/dev/uleds"

    def __init__(self, name: str, max_brightness: int = 1, **kwargs):
        self.name = name
        self.max_brightness = max_brightness
        self._brightness = None
        super().__init__(self.PATH, **kwargs)

    @staticmethod
    def decode(data):
        return int.from_bytes(data, "little")

    def _on_open(self):
        data = struct.pack("64si", self.name.encode(), self.max_brightness)
        self._fobj.write(data)
        self._brightness = self.brightness

    def read(self):
        if not self.is_blocking:
            select.select((self,), (), ())
        return self.raw_read()

    def raw_read(self):
        return self._fobj.read()

    def brightness(self):
        data = self.raw_read()
        if data is not None:
            self._brightness = self.decode(data)
        return self._brightness

    def stream(self):
        while True:
            data = self.read()
            self._brightness = self.decode(data)
            yield self._brightness


def iter_device_paths() -> Iterable[pathlib.Path]:
    yield from LED_PATH.iterdir()


def iter_devices() -> Iterable[Device]:
    return (LED.from_syspath(path) for path in iter_device_paths())


def main():
    for dev in sorted(iter_devices(), key=lambda dev: dev.syspath.stem):
        print(f"{dev.syspath.stem:32} {dev.trigger:16} {dev.brightness:4}")


if __name__ == "__main__":
    main()
