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
from linuxpy.gpio.device import find, LineFlag

with find() as gpio:
    # request lines 5 and 6
    lines = gpio[5, 6]
    lines.flags = LineFlag.ACTIVE_LOW
    with lines:
        print(lines[:])

```
"""

import collections
import fcntl
import functools
import operator
import os
import pathlib
import selectors

from linuxpy.ctypes import sizeof
from linuxpy.device import BaseDevice, ReentrantOpen, iter_device_files
from linuxpy.gpio import raw
from linuxpy.gpio.raw import IOC
from linuxpy.ioctl import ioctl
from linuxpy.types import Collection, Iterable, PathLike, Sequence
from linuxpy.util import astream, chunks, make_find

Info = collections.namedtuple("Info", "name label lines")
ChipInfo = collections.namedtuple("ChipInfo", "name label lines")
LineInfo = collections.namedtuple("LineInfo", "name consumer offset flags attributes")

LineFlag = raw.LineFlag
LineAttrId = raw.LineAttrId
LineEventId = raw.LineEventId
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
        if attr.id == LineAttrId.FLAGS:
            attributes.flags = LineFlag(attr.flags)
        elif attr.id == LineAttrId.OUTPUT_VALUES:
            attributes.indexes = [x for x, y in enumerate(bin(attr.values)[2:][::-1]) if y != "0"]
        elif attr.id == LineAttrId.DEBOUNCE:
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


def request_line(fd, consumer_name: str, lines: Sequence[int], flags: LineFlag, blocking=False):
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
        LineEventId(event.id),
        event.offset,
        event.seqno,
        event.line_seqno,
    )


def event_selector(fds: Collection[int]) -> selectors.BaseSelector:
    selector = selectors.DefaultSelector()
    for fd in fds:
        selector.register(fd, selectors.EVENT_READ)
    return selector


def fd_stream(fds: Collection[int], timeout: float | None = None):
    selector = event_selector(fds)
    while True:
        for key, _ in selector.select(timeout):
            yield key.fileobj


def event_stream(fds: Collection[int], timeout: float | None = None):
    for fd in fd_stream(fds, timeout):
        yield read_one_event(fd)


async def async_fd_stream(fds: Collection[int]):
    selector = event_selector(fds)
    async for events in astream(selector, selector.select):
        for key, _ in events:
            yield key.fileobj


async def async_event_stream(fds: Collection[int]):
    async for fd in async_fd_stream(fds):
        yield read_one_event(fd)


class LineRequest(ReentrantOpen):
    def __init__(self, device, lines: Sequence[int], name: str = "", flags: LineFlag = LineFlag(0)):
        assert len(lines) <= 64
        self.device = device
        self.name = name
        self.flags = flags
        self.lines = lines
        self.indexes = {line: index for index, line in enumerate(lines)}
        self.request = None
        super().__init__()

    def __iter__(self):
        return event_stream((self,))

    async def __aiter__(self):
        async for event in async_event_stream((self,)):
            yield event

    def __getitem__(self, key: int | tuple | slice):
        """Get values"""
        if isinstance(key, int):
            return self.get_values((key,))[key]
        if isinstance(key, slice):
            key = self.lines[key]
        return self.get_values(key)

    def fileno(self):
        return self.request.fd

    def close(self):
        if self.request is None:
            return
        os.close(self.request.fd)
        self.request = None

    def open(self):
        self.request = request_line(self.device, self.name, self.lines, self.flags)

    def get_values(self, lines: Collection[int] | None = None) -> dict[int, int]:
        if lines is None:
            lines = self.lines

        mask = functools.reduce(operator.or_, (1 << self.indexes[line] for line in lines), 0)
        values = get_values(self, mask)
        return {line: (values.bits >> self.indexes[line]) & 1 for line in lines}

    def set_values(self, values: dict[int, int | bool]):
        mask, bits = 0, 0
        for line, value in values.items():
            index = self.indexes[line]
            mask |= 1 << index
            if value:
                bits |= 1 << index
        return set_values(self, mask, bits)

    def read_one(self) -> LineEvent:
        return next(iter(self))


class Request(ReentrantOpen):
    def __init__(self, device, lines: list[int] | tuple[int], name: str = "", flags: LineFlag = LineFlag(0)):
        self.lines = lines
        self.line_requests = []
        self.line_map = {}
        for chunk in chunks(lines, 64):
            line_request = LineRequest(device, chunk, name, flags)
            self.line_requests.append(line_request)
            for line in chunk:
                self.line_map[line] = line_request
        super().__init__()

    def iter_fileno(self):
        return (request.fd for request in self.requests)

    def __iter__(self):
        return event_stream(self.line_requests)

    async def __aiter__(self):
        async for event in async_event_stream(self.line_requests):
            yield event

    def __getitem__(self, key: int | tuple | slice):
        """Get values"""
        if isinstance(key, int):
            return self.get_values((key,))[key]
        if isinstance(key, slice):
            key = self.lines[key]
        return self.get_values(key)

    def close(self):
        for line_request in self.line_requests:
            line_request.close()

    def open(self):
        for line_request in self.line_requests:
            line_request.open()

    def get_values(self, lines: None | list[int] | tuple[int] = None):
        if lines is None:
            lines = self.lines
        request_lines = {}
        for line in lines:
            request_line = self.line_map[line]
            request_lines.setdefault(request_line, []).append(line)
        result = {}
        for request_line, local_lines in request_lines.items():
            result.update(request_line.get_values(local_lines))
        return result

    def set_values(self, values: dict[int, int | bool]):
        request_lines = {}
        for line, value in values.items():
            request_line = self.line_map[line]
            request_lines.setdefault(request_line, {})[line] = value
        for request_line, local_lines in request_lines.items():
            request_line.set_values(local_lines)

    def read_one(self) -> LineEvent:
        return next(iter(self))


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
        """Request line(s)"""
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
