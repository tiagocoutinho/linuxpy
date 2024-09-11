#
# This file is part of the linuxpy project
#
# Copyright (c) 2024 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

"""
Human friendly interface to linux GPIO subsystem.

The heart of linuxpy GPIO library is the [`Device`][linuxpy.gio.device.Device]
class.
The recommended way is to use one of the find methods to create a Device object
and use it within a context manager like:

```python
from linuxpy.gpio.device import ...

```
"""

import collections
from pathlib import Path

from linuxpy.device import BaseDevice, iter_device_files
from linuxpy.gpio import raw
from linuxpy.gpio.raw import IOC
from linuxpy.ioctl import ioctl
from linuxpy.types import Iterable, PathLike
from linuxpy.util import make_find

Info = collections.namedtuple("Info", "name label lines")
ChipInfo = collections.namedtuple("ChipInfo", "name label lines")
LineInfo = collections.namedtuple("LineInfo", "name consumer offset flags attributes")


class LineAttributes:
    def __init__(self):
        self.flags = raw.GpioV2LineFlag(0)
        self.indexes = []
        self.debounce_period = 0

    def __repr__(self):
        return f"Attrs(flags={self.flags}, indexes={self.indexes}, debounce_period={self.debounce_period})"


def get_chip_info(fd):
    info = raw.gpiochip_info()
    ioctl(fd, IOC.CHIPINFO, info)
    return ChipInfo(info.name.decode(), info.label.decode(), info.lines)


def get_line_info(fd, line: int):
    info = raw.gpio_v2_line_info(offset=line)
    ioctl(fd, IOC.GET_LINEINFO, info)
    attributes = LineAttributes()
    for i in range(info.num_attrs):
        attr = info.attrs[i]
        if attr.id == raw.GpioV2LineAttrId.FLAGS:
            attributes.flags = raw.GpioV2LineFlag(attr.flags)
        elif attr.id == raw.GpioV2LineAttrId.OUTPUT_VALUES:
            attributes.indexes = [x for x, y in enumerate(bin(attr.values)[2:][::-1]) if y != "0"]
        elif attr.id == raw.GpioV2LineAttrId.DEBOUNCE:
            attributes.debounce_period = attr.debounce_period_us / 1_000_000

    return LineInfo(
        info.name.decode(),
        info.consumer.decode(),
        info.offset,
        raw.GpioV2LineFlag(info.flags),
        attributes,
    )


def get_info(fd):
    chip = get_chip_info(fd)
    return Info(chip.name, chip.label, [get_line_info(fd, line) for line in range(chip.lines)])


def get_line(fd, consumer_name: str, lines, flags: raw.GpioV2LineFlag):
    num_lines = len(lines)
    req = raw.gpio_v2_line_request()
    req.consumer = consumer_name.encode()
    req.num_lines = num_lines
    req.offsets[:num_lines] = lines
    req.config.flags = flags
    req.config.num_attrs = 0  # for now only support generic config
    return ioctl(fd, IOC.GET_LINE, req)


class Device(BaseDevice):
    PREFIX = "/dev/gpiochip"

    def get_info(self):
        return get_info(self)


def iter_gpio_files(path: PathLike = "/dev") -> Iterable[Path]:
    """Returns an iterator over all GPIO chip files"""
    return iter_device_files(path=path, pattern="gpio*")


def iter_devices(path: PathLike = "/dev", **kwargs) -> Iterable[Device]:
    """Returns an iterator over all GPIO chip devices"""
    return (Device(name, **kwargs) for name in iter_gpio_files(path=path))


find = make_find(iter_devices)
