#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

"""
Human friendly interface to linux thermal subsystem.

The heart of linuxpy thermal library are the [`ThermalZone`][linuxpy.thermal.ThermalZone]
and [`CoolingDevice`][linuxpy.thermal.CoolingDevice] classes.

Probably the most common way to create a thermal device is through
the [`find`][linuxpy.thermal.find] helper:

```python
with find(type="x86_pkg_temp") as tz:
    print(f"X86 temperature: {tz.temperature/1000:6.2f} C")
```
"""

import pathlib
import time

from linuxpy.device import device_number
from linuxpy.sysfs import THERMAL_PATH, Attr, Device, Int, Mode, Str
from linuxpy.types import Callable, Iterable, Optional, Union
from linuxpy.util import make_find


class ThermalZone(Device):
    """
    Thermal sensor

    Attributes:
        type (str): thermal zone type
        policy (str): the policy
        available_policies list[str]: list of available policies
        temperature (int): current temperature in milli-celsius
        offset (int): offet in milli-celsius
        mode (Mode): current mode (enabled/disabled)
        device_number (int): thermal device number
        trip_points (list[TripPoint]): list of trip points (new list every time)
    """

    type = Str("type")
    policy = Str("policy")
    available_policies = Attr("available_policies", str.split)
    temperature = Int("temp")
    offset = Int("offset")
    mode = Attr("mode", Mode)

    @classmethod
    def from_id(cls, n):
        return cls.from_syspath(THERMAL_PATH / f"thermal_zone{n}")

    @property
    def trip_points(self):
        result = []
        for temp_path in self.syspath.glob("trip_point_*_temp"):
            type_path = temp_path.with_name(temp_path.name.replace("_temp", "_type"))
            result.append(TripPoint(temp_path, type_path))
        return result

    @property
    def device_number(self) -> Optional[int]:
        return device_number(self.syspath)


class TripPoint:
    """
    Trip point associated with the thermal zone

    Attributes:
        temperature (int): trip point temperature in milli-celsius
        type (str): trip point type
    """

    def __init__(self, temperature_path, type_path):
        self.temperature_path = temperature_path
        self.type_path = type_path

    @property
    def temperature(self) -> int:
        with self.temperature_path.open() as f:
            return int(f.read())

    @property
    def type(self) -> str:
        with self.type_path.open() as f:
            return f.read().strip()


class CoolingDevice(Device):
    """
    Cooling device (fan, processor, ...)

    Attributes:
        type (str): thermal zone type
    """

    type = Str("type")
    state = Int("cur_state")
    max_state = Int("max_state")

    @property
    def device_number(self) -> Optional[int]:
        return device_number(self.syspath)


def iter_thermal_zone_paths() -> Iterable[pathlib.Path]:
    """Returns an iterator over all thermal zone paths"""
    yield from THERMAL_PATH.glob("thermal_zone*")


def iter_thermal_zone_devices() -> Iterable[ThermalZone]:
    """Returns an iterator over all thermal zone devices"""
    return (ThermalZone.from_syspath(path) for path in iter_thermal_zone_paths())


def iter_cooling_device_paths() -> Iterable[pathlib.Path]:
    """Returns an iterator over all cooling device paths"""
    yield from THERMAL_PATH.glob("cooling_device*")


def iter_cooling_devices() -> Iterable[CoolingDevice]:
    """Returns an iterator over all cooling devices"""
    return (CoolingDevice.from_syspath(path) for path in iter_cooling_device_paths())


def iter_devices() -> Iterable[Union[ThermalZone, CoolingDevice]]:
    """Returns an iterator over all thermal and cooling devices"""
    yield from iter_thermal_zone_devices()
    yield from iter_cooling_devices()


_find = make_find(iter_devices)


def find(
    find_all: bool = False, custom_match: Optional[Callable] = None, **kwargs
) -> Union[Device, Iterable[Device], None]:
    """
    If find_all is False:

    Find a device follwing the criteria matched by custom_match and kwargs.
    If no device is found matching the criteria it returns None.
    Default is to return a random first device.

    If find_all is True:

    The result is an iterator.
    Find all devices that match the criteria custom_match and kwargs.
    If no device is found matching the criteria it returns an empty iterator.
    Default is to return an iterator over all input devices found on the system.
    """
    return _find(find_all, custom_match, **kwargs)


def main():
    def acq():
        for dev in sorted(iter_thermal_zone_devices(), key=lambda dev: dev.type):
            yield dev, dev.temperature

    while True:
        read = acq()
        print(" | ".join(f"{dev.type} = {temp / 1000:6.2f}" for dev, temp in read), end="\r")
        time.sleep(0.1)


if __name__ == "__main__":
    main()
