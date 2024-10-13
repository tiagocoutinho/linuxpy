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
    """Reads the chip information

    Args:
        fd (FDLike): a gpiochip file number or file like object

    Returns:
        ChipInfo: chip info of the given file descriptor
    """
    info = raw.gpiochip_info()
    ioctl(fd, IOC.CHIPINFO, info)
    return ChipInfo(info.name.decode(), info.label.decode(), info.lines)


def get_line_info(fd: FDLike, line: int) -> LineInfo:
    """Reads the given line information

    Args:
        fd (FDLike): a gpiochip file number or file like object
        line (int): desired line to get information

    Returns:
        LineInfo: information for the given line and chip
    """
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
    """Reads the given chip the full information

    Args:
        fd (FDLike): a gpiochip file number or file like object

    Returns:
        Info: information for the given chip including all its lines
    """
    chip = get_chip_info(fd)
    return Info(chip.name, chip.label, [get_line_info(fd, line) for line in range(chip.lines)])


def request_line(
    fd: FDLike, consumer_name: str, lines: Sequence[int], flags: LineFlag, blocking=False
) -> raw.gpio_v2_line_request:
    """Make a request to reserve the given line(s)

    Args:
        fd (FDLike): a gpiochip file number or file like object
        consumer_name (str): consumer name (max 32 chars)
        lines (Sequence[int]): list of lines to reserve
        flags (LineFlag): common flags
        blocking (bool, optional): Make the return FD blocking. Defaults to False.

    Returns:
        raw.gpio_v2_line_request: The details of the request. Field `fd` contains the new open file descritor
    """
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
    """Read lines values.

    Args:
        req_fd (FDLike): a gpiochip file number or file like object
        mask (int): a bitmap identifying the lines, with each bit number corresponding to
                    the index of the line reserved in the given req_fd.

    Returns:
        raw.gpio_v2_line_values: the current line values
    """
    result = raw.gpio_v2_line_values(mask=mask)
    return ioctl(req_fd, IOC.LINE_GET_VALUES, result)


def set_values(req_fd: FDLike, mask: int, bits: int) -> raw.gpio_v2_line_values:
    """
    Set lines values.

    Args:
        req_fd (FDLike): a gpiochip file number or file like object
        mask: The mask is a bitmap identifying the lines, with each bit number corresponding to
              the index of the line reserved in the given req_fd.
        bits: The bits is a bitmap containing the value of the lines, set to 1 for active and 0
              for inactive.

    Returns:
        raw.gpio_v2_line_values: the underlying object sent to the ioctl call
    """
    result = raw.gpio_v2_line_values(mask=mask, bits=bits)
    return ioctl(req_fd, IOC.LINE_SET_VALUES, result)


def read_one_event(req_fd: FDLike) -> LineEvent:
    """Read one event from the given request file descriptor

    Args:
        req_fd (FDLike): _description_

    Returns:
        LineEvent: _description_
    """
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
    """A lazy request to reserve lines on a chip

    Prefered creation from the `Device.request()` method.
    """

    def __init__(
        self, device, lines: Sequence[int], name: str = "", flags: LineFlag = LineFlag(0), blocking: bool = False
    ):
        self.lines = lines
        self._name = name
        self._flags = flags
        self.line_requests: list[_Request] = []
        self.line_map: dict[int, _Request] = {}
        for chunk in chunks(lines, 64):
            line_request = _Request(device, chunk, name, flags, blocking)
            self.line_requests.append(line_request)
            for line in chunk:
                self.line_map[line] = line_request
        super().__init__()

    @property
    def name(self) -> str:
        """Requestor name

        Change the requestor name must be called before the request is open
        to take effect

        Returns:
            str: consumer name
        """
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        """Set requestor name. Must be called before the request is open
        to take effect

        Args:
            name (str): new requestor name
        """
        self._name = name
        for req in self.line_requests:
            req.name = name

    @property
    def flags(self) -> LineFlag:
        return self._flags

    @flags.setter
    def flags(self, flags: LineFlag):
        self._flags = flags
        for req in self.line_requests:
            req.flags = flags

    def __getitem__(self, key: Union[int, tuple, slice]) -> Union[int, dict]:
        """Reads lines values

        Args:
            key (Union[int, tuple, slice]): a line number, a slice, or a list of line numbers or slices

        Returns:
            Union[int, dict]: a dict where key is line number and value its value
        """
        if isinstance(key, int):
            return self.get_values((key,))[key]
        lines = expand_from_list(key, self.min_line, self.max_line + 1)
        return self.get_values(lines)

    def __setitem__(self, key: Union[int, tuple, slice], value: Union[int, Sequence[int]]):
        """Sets the given lines values

        Args:
            key (Union[int, tuple, slice]): a line number, a slice, or a list of line numbers or slices
            value (Union[int, Sequence[int]]): the value(s) to write for the given lines

        Raises:
            ValueError: if key is a line number and value is not a number (0 or 1)
        """
        if isinstance(key, int):
            if not isinstance(value, int):
                raise ValueError("set value for single line must be 0 or 1")
            values = {key: value}
        else:
            lines = expand_from_list(key, self.min_line, self.max_line + 1)
            if isinstance(value, int):
                value = len(lines) * (value,)
            values = dict(zip(lines, value))
        self.set_values(values)

    def __iter__(self) -> Iterable[LineEvent]:
        """Infinite stream of line events

        Returns:
            Iterable[LineEvent]: the stream of events
        """
        return event_stream(self.filenos())

    def __aiter__(self) -> AsyncIterator[LineEvent]:
        """Asynchronous stream of line events

        Returns:
            AsyncIterator[LineEvent]: the asynchronous stream of events
        """
        return async_event_stream(self.filenos())

    @property
    def min_line(self) -> int:
        """The smallest line number in the request

        Returns:
            int: The smallest line number in the request
        """
        if not hasattr(self, "_min_line"):
            self._min_line = min(self.lines)
        return self._min_line

    @property
    def max_line(self) -> int:
        """The biggest line number in the request

        Returns:
            int: The biggest line number in the request
        """
        if not hasattr(self, "_max_line"):
            self._max_line = max(self.lines)
        return self._max_line

    def filenos(self) -> list[int]:
        """List of underlying request file numbers

        Returns:
            list[int]: List of underlying request file numbers
        """
        return [request.fd for request in self.line_requests]

    def close(self):
        """Closes the underling request files. If request is not
        open nothing is done.
        """
        for line_request in self.line_requests:
            line_request.close()

    def open(self):
        """Opens the underling request files effectively reserving the lines"""
        for line_request in self.line_requests:
            line_request.open()

    def get_values(self, lines: Optional[Sequence[int]] = None) -> dict[int, int]:
        """Reads values for the given lines

        Args:
            lines (Optional[Sequence[int]], optional): A collection of lines. Defaults to None. Default means read all lines

        Returns:
            dict[int, int]: line values. Key is line number and value its value
        """
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
        """Writes new values on the given lines

        Args:
            values (dict[int, Union[int, bool]]): key is line number and value its value
        """
        request_lines = {}
        for line, value in values.items():
            request_line = self.line_map[line]
            request_lines.setdefault(request_line, {})[line] = value
        for request_line, local_lines in request_lines.items():
            request_line.set_values(local_lines)


class Device(BaseDevice):
    """A device represents a connection to the underlying gpio chip"""

    PREFIX = "/dev/gpiochip"

    def __len__(self) -> int:
        """The number of lines in this chip

        Returns:
            int: The number of lines in this chip
        """
        if not hasattr(self, "_len"):
            self._len = get_chip_info(self).lines
        return self._len

    def __getitem__(self, key: Union[int, tuple, slice]) -> Request:
        """create a request for the given lines. Equivalent to `device.request(key)`

        !!! note

            The request is not active after this call. You need to use the request object returned
            by this method in a context manager or manually call open/close.

        Args:
            key (Union[int, tuple, slice]): the line number, slice or a list of line numbers, or slices

        Returns:
            Request: A new request object
        """
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
        """Create a request to reserve a list of lines on this chip

        !!! note

            The request is not active after this call. You need to use the request object returned
            by this method in a context manager or manually call open/close.

        Args:
            lines (Optional[Sequence[int]], optional): Lists of lines. Defaults to None. Default is to reserve all lines
            name (str, optional): the requestor (aka consumer) name. Defaults to "".
            flags (LineFlag, optional): Flags on the request. Defaults to LineFlag(0).

        Returns:
            Request: A new request object
        """
        if lines is None:
            lines = list(range(len(self)))
        return Request(self, lines, name, flags)


def iter_gpio_files(path: PathLike = "/dev") -> Iterable[pathlib.Path]:
    """Returns an iterator over all GPIO chip files.

    !!! warning
        Only files for which the current user has read and write access are returned

    Args:
        path (PathLike, optional): root path. Defaults to "/dev".

    Returns:
        Iterable[pathlib.Path]: an iterator over the gpiochip files found on the system
    """
    return iter_device_files(path=path, pattern="gpio*")


def iter_devices(path: PathLike = "/dev", **kwargs) -> Iterable[Device]:
    """Returns an iterator over all GPIO chip devices

    Args:
        path (PathLike, optional): root path. Defaults to "/dev".

    Returns:
        Iterable[Device]:  an iterator over the gpiochip devices found on the system
    """
    return (Device(name, **kwargs) for name in iter_gpio_files(path=path))


find = make_find(iter_devices, needs_open=False)
