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
import fcntl
import os
import pathlib
import selectors

from linuxpy.ctypes import sizeof
from linuxpy.device import BaseDevice, ReentrantOpen, iter_device_files
from linuxpy.gpio import raw
from linuxpy.gpio.raw import IOC
from linuxpy.ioctl import ioctl
from linuxpy.types import Iterable, PathLike
from linuxpy.util import astream, chunks, make_find

Info = collections.namedtuple("Info", "name label lines")
ChipInfo = collections.namedtuple("ChipInfo", "name label lines")
LineInfo = collections.namedtuple("LineInfo", "name consumer offset flags attributes")

LineFlag = raw.GpioV2LineFlag
LineEvent = collections.namedtuple("LineEvent", "timestamp type line sequence line_sequence")


class LineAttributes:
    def __init__(self):
        self.flags = raw.GpioV2LineFlag(0)
        self.indexes = []
        self.debounce_period = 0

    def __repr__(self):
        return f"Attrs(flags={self.flags}, indexes={self.indexes}, debounce_period={self.debounce_period})"


def get_chip_info(fd) -> ChipInfo:
    info = raw.gpiochip_info()
    ioctl(fd, IOC.CHIPINFO, info)
    return ChipInfo(info.name.decode(), info.label.decode(), info.lines)


def get_line_info(fd, line: int) -> LineInfo:
    info = raw.gpio_v2_line_info(offset=line)
    ioctl(fd, IOC.GET_LINEINFO, info)
    attributes = LineAttributes()
    for i in range(info.num_attrs):
        attr = info.attrs[i]
        if attr.id == raw.GpioV2LineAttrId.FLAGS:
            attributes.flags = LineFlag(attr.flags)
        elif attr.id == raw.GpioV2LineAttrId.OUTPUT_VALUES:
            attributes.indexes = [x for x, y in enumerate(bin(attr.values)[2:][::-1]) if y != "0"]
        elif attr.id == raw.GpioV2LineAttrId.DEBOUNCE:
            attributes.debounce_period = attr.debounce_period_us / 1_000_000

    return LineInfo(
        info.name.decode(),
        info.consumer.decode(),
        info.offset,
        LineFlag(info.flags),
        attributes,
    )


def get_info(fd) -> Info:
    chip = get_chip_info(fd)
    return Info(chip.name, chip.label, [get_line_info(fd, line) for line in range(chip.lines)])


def get_line(fd, consumer_name: str, lines, flags: LineFlag, blocking=False):
    num_lines = len(lines)
    req = raw.gpio_v2_line_request()
    req.consumer = consumer_name.encode()
    req.num_lines = num_lines
    req.offsets[:num_lines] = lines
    req.config.flags = flags
    req.config.num_attrs = 0  # for now only support generic config
    ioctl(fd, IOC.GET_LINE, req)
    if not blocking:
        flag = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(req.fd, fcntl.F_SETFL, flag | os.O_NONBLOCK)
    return req


def get_values(req_fd, mask: int) -> raw.gpio_v2_line_values:
    result = raw.gpio_v2_line_values(mask=mask)
    return ioctl(req_fd, IOC.LINE_GET_VALUES, result)


def set_values(req_fd, mask: int, bits: int) -> raw.gpio_v2_line_values:
    result = raw.gpio_v2_line_values(mask=mask, bits=bits)
    return ioctl(req_fd, IOC.LINE_SET_VALUES, result)


def read_one_event(req_fd) -> LineEvent:
    data = os.read(req_fd, sizeof(raw.gpio_v2_line_event))
    event = raw.gpio_v2_line_event.from_buffer_copy(data)
    return LineEvent(
        event.timestamp_ns * 1e-9,
        raw.GpioV2LineEventId(event.id),
        event.offset,
        event.seqno,
        event.line_seqno,
    )


def event_selector(fds: list[int]) -> selectors.BaseSelector:
    selector = selectors.DefaultSelector()
    for fd in fds:
        selector.register(fd, selectors.EVENT_READ)
    return selector


def fd_stream(fds: list[int], timeout: float | None = None):
    selector = event_selector(fds)
    while True:
        for key, _ in selector.select(timeout):
            yield key.fileobj


def event_stream(fds: list[int], timeout: float | None = None):
    for fd in fd_stream(fds, timeout):
        yield read_one_event(fd)


async def async_fd_stream(fds: list[int]):
    selector = event_selector(fds)
    async for events in astream(selector, selector.select):
        for key, _ in events:
            yield key.fileobj


async def async_event_stream(fds: list[int]):
    async for fd in async_fd_stream(fds):
        yield read_one_event(fd)


class Request(ReentrantOpen):
    def __init__(self, device, lines: list[int] | tuple[int], name: str = "", flags: LineFlag = LineFlag(0)):
        self.device = device
        self.name = name
        self.flags = flags
        self.indexes = {}
        self.lines = lines
        self.chunk_lines = []
        for chunk_nb, chunk in enumerate(chunks(lines, 64)):
            chunk_lines = []
            for index, line in enumerate(chunk):
                self.indexes[line] = chunk_nb, index
                chunk_lines.append(line)
            self.chunk_lines.append(chunk_lines)
        self.requests = None
        super().__init__()

    def iter_fileno(self):
        return (request.fd for request in self.requests)

    def __iter__(self):
        return event_stream(self.iter_fileno())

    async def __aiter__(self):
        async for event in async_event_stream(self.iter_fileno()):
            yield event

    def __getitem__(self, key: int | tuple | slice):
        """Get values"""
        if isinstance(key, int):
            key = (key,)
        elif isinstance(key, slice):
            key = self.lines[key]
        return self.get_values(key)

    def close(self):
        for request in self.requests or ():
            os.close(request.fd)
        self.requests = None

    def open(self):
        self.requests = tuple(get_line(self.device, self.name, lines, self.flags) for lines in self.chunk_lines)

    def get_values(self, lines: None | list[int] | tuple[int] = None):
        if lines is None:
            lines = tuple(line for lines in self.chunk_lines for line in lines)

        chunks = {}
        for line in lines:
            chunk_nb, index = self.indexes[line]
            chunks[chunk_nb] = chunks.get(chunk_nb, 0) | 1 << index

        values = {}
        for chunk_nb, mask in chunks.items():
            request = self.requests[chunk_nb]
            values[chunk_nb] = get_values(request.fd, mask)

        results = {}
        for line in lines:
            chunk_nb, index = self.indexes[line]
            results[line] = values[chunk_nb].bits >> index & 0b1
        return results

    def set_values(self, values: dict[int, int | bool]):
        chunks = {}
        for line, value in values.items():
            chunk_nb, index = self.indexes[line]
            mask, bits = chunks.get(chunk_nb, (0, 0))
            mask |= 1 << index
            if value:
                bits |= 1 << index
            chunks[chunk_nb] = mask, bits

        for chunk_nb, (mask, bits) in chunks.items():
            request = self.requests[chunk_nb]
            set_values(request.fd, mask, bits)

    def read_one(self) -> LineEvent:
        fd = next(iter(self))
        return read_one_event(fd)


class Device(BaseDevice):
    PREFIX = "/dev/gpiochip"

    def get_info(self) -> Info:
        return get_info(self)

    def request(self, lines: list[int] | tuple[int] | None = None, name: str = "", flags: LineFlag = LineFlag(0)):
        if lines is None:
            chip_info = get_chip_info(self)
            lines = tuple(range(0, chip_info.lines))
        return Request(self, lines, name, flags)

    def __getitem__(self, key: int | tuple | slice):
        """Request line"""
        if isinstance(key, int):
            key = (key,)
        elif isinstance(key, slice):
            chip_info = get_chip_info(self)
            key = tuple(range(*key.indices(chip_info.lines)))
        return self.request(key)


def iter_gpio_files(path: PathLike = "/dev") -> Iterable[pathlib.Path]:
    """Returns an iterator over all GPIO chip files"""
    return iter_device_files(path=path, pattern="gpio*")


def iter_devices(path: PathLike = "/dev", **kwargs) -> Iterable[Device]:
    """Returns an iterator over all GPIO chip devices"""
    return (Device(name, **kwargs) for name in iter_gpio_files(path=path))


find = make_find(iter_devices)
