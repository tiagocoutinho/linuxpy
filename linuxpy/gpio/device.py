#
# This file is part of the linuxpy project
#
# Copyright (c) 2024 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

"""
Human friendly interface to linux GPIO subsystem.

The heart of linuxpy GPIO library is the [`Device`][linuxpy.gpio.device.Device]
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

from linuxpy.ctypes import sizeof
from linuxpy.device import BaseDevice, ReentrantOpen, iter_device_files
from linuxpy.gpio import raw
from linuxpy.gpio.raw import IOC
from linuxpy.ioctl import ioctl
from linuxpy.types import AsyncIterator, Collection, FDLike, Iterable, Optional, PathLike, Sequence, Union
from linuxpy.util import async_event_stream as async_events, bit_indexes, chunks, event_stream as events, make_find

Info = collections.namedtuple("Info", "name label lines")
ChipInfo = collections.namedtuple("ChipInfo", "name label lines")
LineInfo = collections.namedtuple("LineInfo", "name consumer offset flags attributes")

LineFlag = raw.LineFlag
LineAttrId = raw.LineAttrId
LineEventId = raw.LineEventId
LineEvent = collections.namedtuple("LineEvent", "timestamp type line sequence line_sequence")


class LineAttributes:
    def __init__(self):
        self.flags = LineFlag(0)
        self.indexes = []
        self.debounce_period = 0


def get_chip_info(fd: FDLike) -> ChipInfo:
    """Reads the chip information"""
    info = raw.gpiochip_info()
    ioctl(fd, IOC.CHIPINFO, info)
    return ChipInfo(info.name.decode(), info.label.decode(), info.lines)


def get_line_info(fd: FDLike, line: int) -> LineInfo:
    """Reads the given line information"""
    info = raw.gpio_v2_line_info(offset=line)
    ioctl(fd, IOC.GET_LINEINFO, info)
    attributes = LineAttributes()
    for i in range(info.num_attrs):
        attr = info.attrs[i]
        if attr.id == LineAttrId.FLAGS:
            attributes.flags = LineFlag(attr.flags)
        elif attr.id == LineAttrId.OUTPUT_VALUES:
            attributes.indexes = bit_indexes(attr.values)
        elif attr.id == LineAttrId.DEBOUNCE:
            attributes.debounce_period = attr.debounce_period_us / 1_000_000

    return LineInfo(
        info.name.decode(),
        info.consumer.decode(),
        info.offset,
        LineFlag(info.flags),
        attributes,
    )


def get_info(fd: FDLike) -> Info:
    """Reads the given line information"""
    chip = get_chip_info(fd)
    return Info(chip.name, chip.label, [get_line_info(fd, line) for line in range(chip.lines)])


def request_line(
    fd: FDLike, consumer_name: str, lines: Sequence[int], flags: LineFlag, blocking=False
) -> raw.gpio_v2_line_request:
    """Make a request to reserve the given line(s)"""
    num_lines = len(lines)
    req = raw.gpio_v2_line_request()
    req.consumer = consumer_name.encode()
    req.num_lines = num_lines
    req.offsets[:num_lines] = lines
    req.config.flags = flags
    req.config.num_attrs = 0  # for now only support generic config
    ioctl(fd, IOC.GET_LINE, req)
    if not blocking:
        flag = fcntl.fcntl(req.fd, fcntl.F_GETFL)
        fcntl.fcntl(req.fd, fcntl.F_SETFL, flag | os.O_NONBLOCK)
    return req


def get_values(req_fd: FDLike, mask: int) -> raw.gpio_v2_line_values:
    """
    Read line values.
    The mask is a bitmap identifying the lines, with each bit number corresponding to
    the index of the line reserved in the given req_fd.
    """
    result = raw.gpio_v2_line_values(mask=mask)
    return ioctl(req_fd, IOC.LINE_GET_VALUES, result)


def set_values(req_fd: FDLike, mask: int, bits: int) -> raw.gpio_v2_line_values:
    """
    Set line values.

    Parameters:
        mask: The mask is a bitmap identifying the lines, with each bit number corresponding to
              the index of the line reserved in the given req_fd.
        bits: The bits is a bitmap containing the value of the lines, set to 1 for active and 0
              for inactive.
    """
    print(mask, bits)
    result = raw.gpio_v2_line_values(mask=mask, bits=bits)
    return ioctl(req_fd, IOC.LINE_SET_VALUES, result)


def read_one_event(req_fd: FDLike) -> LineEvent:
    """Read one event from the given request file descriptor"""
    fd = req_fd if isinstance(req_fd, int) else req_fd.fileno()
    data = os.read(fd, sizeof(raw.gpio_v2_line_event))
    event = raw.gpio_v2_line_event.from_buffer_copy(data)
    return LineEvent(
        event.timestamp_ns * 1e-9,
        LineEventId(event.id),
        event.offset,
        event.seqno,
        event.line_seqno,
    )


event_stream = functools.partial(events, read=read_one_event)
async_event_stream = functools.partial(async_events, read=read_one_event)


def expand_from_list(key: Union[int, slice, tuple], minimum, maximum) -> list[int]:
    """Used internally in __getitem__ to expand the given key"""
    if isinstance(key, int):
        return [key]
    if isinstance(key, slice):
        start = minimum if key.start is None else key.start
        key = slice(start, key.stop, key.step)
        return list(range(maximum)[key])
    return [line for item in key for line in expand_from_list(item, minimum, maximum)]


class _Request(ReentrantOpen):
    """Raw line request. Not to be used directly"""

    def __init__(
        self,
        device: "Device",
        lines: Sequence[int],
        name: str = "",
        flags: LineFlag = LineFlag(0),
        blocking: bool = False,
    ):
        assert len(lines) <= 64
        self.device = device
        self.name = name
        self.flags = flags
        self.lines = lines
        self.blocking = blocking
        self.indexes = {line: index for index, line in enumerate(lines)}
        self.fd = -1
        super().__init__()

    def fileno(self) -> int:
        return self.fd

    def close(self):
        if self.fd < 0:
            return
        os.close(self.fd)
        self.fd = -1

    def open(self):
        self.fd: int = request_line(self.device, self.name, self.lines, self.flags, self.blocking).fd

    def get_values(self, lines: Collection[int]) -> dict[int, int]:
        mask = functools.reduce(operator.or_, (1 << self.indexes[line] for line in lines), 0)
        values = get_values(self, mask)
        return {line: (values.bits >> self.indexes[line]) & 1 for line in lines}

    def set_values(self, values: dict[int, Union[int, bool]]) -> raw.gpio_v2_line_values:
        mask, bits = 0, 0
        for line, value in values.items():
            index = self.indexes[line]
            mask |= 1 << index
            if value:
                bits |= 1 << index
        return set_values(self, mask, bits)


class Request(ReentrantOpen):
    def __init__(
        self, device, lines: Sequence[int], name: str = "", flags: LineFlag = LineFlag(0), blocking: bool = False
    ):
        self.lines = lines
        self.line_requests: list[_Request] = []
        self.line_map: dict[int, _Request] = {}
        for chunk in chunks(lines, 64):
            line_request = _Request(device, chunk, name, flags, blocking)
            self.line_requests.append(line_request)
            for line in chunk:
                self.line_map[line] = line_request
        super().__init__()

    def __getitem__(self, key: Union[int, tuple, slice]) -> Union[int, dict]:
        """Get values"""
        if isinstance(key, int):
            return self.get_values((key,))[key]
        lines = expand_from_list(key, self.min_line, self.max_line + 1)
        return self.get_values(lines)

    def __setitem__(self, key: Union[int, tuple, slice], value: Union[int, Sequence[int]]):
        if isinstance(key, int) and isinstance(value, int):
            values = {key: value}
        else:
            lines = expand_from_list(key, self.min_line, self.max_line + 1)
            values = dict(zip(lines, value))
        self.set_values(values)

    def __iter__(self) -> Iterable[LineEvent]:
        return event_stream(self.filenos())

    def __aiter__(self) -> AsyncIterator[LineEvent]:
        return async_event_stream(self.filenos())

    @property
    def min_line(self) -> int:
        if not hasattr(self, "_min_line"):
            self._min_line = min(self.lines)
        return self._min_line

    @property
    def max_line(self) -> int:
        if not hasattr(self, "_max_line"):
            self._max_line = max(self.lines)
        return self._max_line

    def filenos(self) -> list[int]:
        return [request.fd for request in self.line_requests]

    def close(self):
        for line_request in self.line_requests:
            line_request.close()

    def open(self):
        for line_request in self.line_requests:
            line_request.open()

    def get_values(self, lines: Optional[Sequence[int]] = None) -> dict[int, int]:
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

    def set_values(self, values: dict[int, Union[int, bool]]):
        request_lines = {}
        for line, value in values.items():
            request_line = self.line_map[line]
            request_lines.setdefault(request_line, {})[line] = value
        for request_line, local_lines in request_lines.items():
            request_line.set_values(local_lines)


class Device(BaseDevice):
    """
    A device represents a connection to the underlying gpio chip


    """

    PREFIX = "/dev/gpiochip"

    def __len__(self) -> int:
        if not hasattr(self, "_len"):
            self._len = get_chip_info(self).lines
        return self._len

    def __getitem__(self, key: Union[int, tuple, slice]) -> Request:
        """Request line(s)"""
        lines = expand_from_list(key, 0, len(self))
        return self.request(lines)

    def get_info(self) -> Info:
        """
        Reads all information available including chip info and detailed information
        about each chip line information

        Returns:
            Info: The full chip information
        """
        return get_info(self)

    def request(self, lines: Optional[Sequence[int]] = None, name: str = "", flags: LineFlag = LineFlag(0)) -> Request:
        if lines is None:
            lines = list(range(len(self)))
        return Request(self, lines, name, flags)


def iter_gpio_files(path: PathLike = "/dev") -> Iterable[pathlib.Path]:
    """Returns an iterator over all GPIO chip files"""
    return iter_device_files(path=path, pattern="gpio*")


def iter_devices(path: PathLike = "/dev", **kwargs) -> Iterable[Device]:
    """Returns an iterator over all GPIO chip devices"""
    return (Device(name, **kwargs) for name in iter_gpio_files(path=path))


find = make_find(iter_devices, needs_open=False)
