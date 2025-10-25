#
# This file is part of the linuxpy project
#
# Copyright (c) 2024 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import asyncio
import os
import socket
import threading
import time
from contextlib import ExitStack, aclosing, contextmanager
from inspect import isgenerator
from itertools import count
from math import ceil, isclose
from pathlib import Path
from unittest import mock

import pytest

from linuxpy.device import device_number
from linuxpy.gpio import device, raw
from linuxpy.gpio.config import (
    CLine,
    CLineIn,
    CLineOut,
    check_line_config,
    encode_config,
    encode_line_config,
    parse_config,
    parse_config_lines,
)
from linuxpy.gpio.device import (
    Device,
    LineEventId,
    LineFlag,
    expand_from_list,
    iter_devices,
    iter_gpio_files,
)
from linuxpy.gpio.sim import find_gpio_sim_file
from linuxpy.util import bit_indexes


def FD():
    return next(FD._FD)


FD._FD = count(10_001, 2)


class Hardware:
    nb_lines = 100

    def __init__(self, filename="/dev/gpiochip99"):
        self.filename = filename
        self.fd = None
        self.fobj = None
        self.requests = {}
        self.name = b"my-little-GPIO"
        self.label = self.name.replace(b"-", b" ")
        self.lines = [line % 2 for line in range(self.nb_lines)]

    def __enter__(self):
        self.stack = ExitStack()
        opener = mock.patch("linuxpy.io.open", self.open)
        self.stack.enter_context(opener)
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.stack.close()

    def open(self, filename, mode, buffering=-1, opener=None):
        ioctl = mock.patch("linuxpy.ioctl.fcntl.ioctl", self.ioctl)
        fcntl = mock.patch("linuxpy.ioctl.fcntl.fcntl", self.fcntl)
        blocking = mock.patch("linuxpy.device.os.get_blocking", self.get_blocking)
        close = mock.patch("linuxpy.gpio.device.os.close", self.close)
        self.stack.enter_context(ioctl)
        self.stack.enter_context(fcntl)
        self.stack.enter_context(blocking)
        self.stack.enter_context(close)
        self.fd = FD()
        self.fobj = mock.Mock()
        self.fobj.fileno.return_value = self.fd
        self.fobj.get_blocking.return_value = False
        self.fobj.closed = False
        return self.fobj

    def get_blocking(self, fd):
        assert self.fd == fd
        return self.fobj.get_blocking()

    @property
    def closed(self):
        return self.fd is not None

    def select(self, readers, writers, other, timeout=None):
        assert readers[0].fileno() == self.fd
        return readers, writers, other

    def ioctl(self, fd, ioc, arg):  # noqa: C901
        self.ioctl_ioc = ioc
        self.ioctl_arg = arg
        if not isinstance(fd, int):
            fd = fd.fileno()
        if fd == self.fd:
            if ioc == raw.IOC.CHIPINFO:
                arg.name = self.name
                arg.label = self.label
                arg.lines = self.nb_lines
            elif ioc == raw.IOC.GET_LINE:
                reader, writer = socket.socketpair()
                arg.fd = reader.fileno()
                self.requests[arg.fd] = arg, (reader, writer)
            elif ioc == raw.IOC.GET_LINEINFO:
                arg.name = f"Line{arg.offset}".encode()
                arg.flags = raw.LineFlag.INPUT
                if arg.offset == 1:
                    arg.consumer = b"another fellow"
                    arg.flags = raw.LineFlag.USED | raw.LineFlag.OUTPUT
                    arg.num_attrs = 3
                    arg.attrs[0] = raw.gpio_v2_line_attribute(id=raw.LineAttrId.FLAGS, flags=raw.LineFlag.ACTIVE_LOW)
                    arg.attrs[1] = raw.gpio_v2_line_attribute(id=raw.LineAttrId.OUTPUT_VALUES, values=0)
                    arg.attrs[2] = raw.gpio_v2_line_attribute(id=raw.LineAttrId.DEBOUNCE, debounce_period_us=99_123_456)

        else:
            request, (reader, writer) = self.requests[fd]
            if ioc == raw.IOC.LINE_GET_VALUES:
                bits = 0
                for index in bit_indexes(arg.mask):
                    line = request.offsets[index]
                    value = self.lines[line]
                    bits |= value << index
                arg.bits = bits
            elif ioc == raw.IOC.LINE_SET_VALUES:
                for index in bit_indexes(arg.mask):
                    line = request.offsets[index]
                    value = (arg.bits >> index) & 1
                    self.lines[line] = value

    def close(self, fd):
        del self.requests[fd]

    def fcntl(self, fd, cmd, arg=0):
        assert fd in self.requests
        return 0

    def trigger_event(
        self,
        fd,
        line: int,
        event_type: LineEventId = LineEventId.RISING_EDGE,
        seqno: int = 2,
        line_seqno: int = 1,
        timestamp_ns: int = 1_000_000,
    ):
        if not isinstance(fd, int):
            fd = fd.fileno()
        _, (reader, writer) = self.requests[fd]
        event = raw.gpio_v2_line_event(
            timestamp_ns=timestamp_ns, id=event_type, offset=line, seqno=seqno, line_seqno=line_seqno
        )
        writer.sendall(bytes(event))


@contextmanager
def gpio_files(paths=("/dev/gpiochip99")):
    with mock.patch("linuxpy.device.pathlib.Path.glob") as glob:
        expected_files = list(paths)
        glob.return_value = expected_files
        with mock.patch("linuxpy.device.pathlib.Path.is_char_device") as is_char_device:
            is_char_device.return_value = True
            with mock.patch("linuxpy.device.os.access") as access:
                access.return_value = os.R_OK | os.W_OK
                yield paths


@pytest.fixture
def chip():
    with Hardware() as hardware:
        yield hardware


def test_encode_line_config():
    line, flags, debounce = encode_line_config({"line": 5})
    assert line == 5
    assert flags == LineFlag.INPUT
    assert debounce is None

    line_config = {
        "line": 5,
        "direction": "output",
    }
    line, flags, debounce = encode_line_config(line_config)
    assert line == line_config["line"]
    assert flags == LineFlag.OUTPUT
    assert debounce is None


def test_check_encode_line_config_errors():
    with pytest.raises(KeyError):
        check_line_config({})

    with pytest.raises(ValueError):
        check_line_config({"line": "hello"})

    with pytest.raises(ValueError):
        check_line_config({"line": -5})

    with pytest.raises(ValueError):
        check_line_config({"line": 1, "direction": "output", "edge": "rising"})

    with pytest.raises(ValueError):
        check_line_config({"line": 1, "direction": "input", "drive": "drain"})

    with pytest.raises(ValueError):
        check_line_config({"line": 1, "direction": "input", "drive": "drain"})

    with pytest.raises(ValueError):
        check_line_config({"line": 1, "direction": "input", "debounce": 0.001})


def test_encode_config():
    result = encode_config([CLineIn(5)])
    assert result.num_attrs == 0
    assert LineFlag(result.flags) == LineFlag.INPUT

    cfg = raw.gpio_v2_line_config()
    result = encode_config([CLineIn(5)], cfg)
    assert result is cfg
    assert result.num_attrs == 0
    assert LineFlag(result.flags) == LineFlag.INPUT

    result = encode_config([CLineIn(5) for i in range(5, 10)])
    assert result.num_attrs == 0
    assert LineFlag(result.flags) == LineFlag.INPUT

    result = encode_config([CLineIn(5), CLineOut(6)])
    assert result.num_attrs == 1
    assert LineFlag(result.flags) == LineFlag.INPUT
    assert result.attrs[0].mask == 0b10
    assert LineFlag(result.attrs[0].attr.flags) == LineFlag.OUTPUT

    result = encode_config([CLineOut(6, debounce=0.02), CLineIn(5)])
    assert result.num_attrs == 2
    assert LineFlag(result.flags) == LineFlag.OUTPUT
    assert LineFlag(result.attrs[0].attr.flags) == LineFlag.INPUT
    assert result.attrs[0].mask == 0b10
    assert result.attrs[1].mask == 0b01
    assert LineFlag(result.attrs[1].attr.debounce_period_us) == 20_000

    result = encode_config(
        [
            CLineOut(6, debounce=0.01),
            CLineIn(5),
            CLineOut(12, drive="drain", debounce=0.01),
            CLineIn(7, edge="rising"),
            CLineIn(55, edge="rising"),
        ]
    )
    assert LineFlag(result.flags) == LineFlag.INPUT | LineFlag.EDGE_RISING
    assert result.num_attrs == 4
    assert result.attrs[0].mask == 0b01
    assert LineFlag(result.attrs[0].attr.flags) == LineFlag.OUTPUT
    assert result.attrs[1].mask == 0b10
    assert LineFlag(result.attrs[1].attr.flags) == LineFlag.INPUT
    assert result.attrs[2].mask == 0b100
    assert LineFlag(result.attrs[2].attr.flags) == LineFlag.OUTPUT | LineFlag.OPEN_DRAIN
    assert result.attrs[3].mask == 0b101
    assert LineFlag(result.attrs[3].attr.debounce_period_us) == 10_000


def test_parse_config_lines():
    assert parse_config_lines(12) == [{"line": 12}]
    assert parse_config_lines((10, 4)) == [{"line": 10}, {"line": 4}]
    assert parse_config_lines([{"line": 10}, {"line": 4}]) == [{"line": 10}, {"line": 4}]
    assert parse_config_lines({10: {}, 4: {}}) == [{"line": 10}, {"line": 4}]


def test_build_config_line():
    fields = (
        ("direction", "output"),
        ("bias", "pull-up"),
        ("drive", "source"),
        ("edge", "falling"),
        ("clock", "hte"),
        ("debounce", 0.001),
    )
    keys, values = [], []
    for key, value in fields:
        keys.append(key)
        values.append(value)
        assert CLine(55, **{key: value}) == {key: value, "line": 55}
        assert CLine(56, *values) == dict(zip(keys, values, strict=True), line=56)


def test_parse_config():
    assert parse_config(None, 16) == {"name": "linuxpy", "lines": [{"line": i} for i in range(16)]}
    assert parse_config(34, 16) == {"name": "linuxpy", "lines": [{"line": 34}]}
    assert parse_config([13, 4], 16) == {"name": "linuxpy", "lines": [{"line": 13}, {"line": 4}]}
    assert parse_config({"lines": [13, 4]}, 16) == {"name": "linuxpy", "lines": [{"line": 13}, {"line": 4}]}
    assert parse_config({"name": "client1", "lines": {4: {}, 12: {}}}, 16) == {
        "name": "client1",
        "lines": [{"line": 4}, {"line": 12}],
    }


def test_expand_list():
    assert [5] == expand_from_list(5, None, None)
    assert [5, 10] == expand_from_list((5, 10), None, None)
    assert list(range(100)) == expand_from_list(slice(100), 0, 100)
    assert list(range(10)) == expand_from_list(slice(10), 0, 100)


@pytest.mark.parametrize("filename, expected", [("/dev/gpiochip0", 0), ("/dev/gpiochip1", 1), ("/dev/gpiochip99", 99)])
def test_device_number(filename, expected):
    assert device_number(filename) == expected


def test_gpio_files():
    with gpio_files(["/dev/gpiochip33", "/dev/gpiochip55"]) as expected_files:
        assert list(iter_gpio_files()) == expected_files


def test_device_list():
    assert isgenerator(iter_devices())

    with gpio_files(["/dev/gpiochip33", "/dev/gpiochip55"]) as expected_files:
        devices = list(iter_devices())
        assert len(devices) == 2
        for dev in devices:
            assert isinstance(dev, Device)
        assert {dev.filename for dev in devices} == {Path(filename) for filename in expected_files}


def test_device_creation():
    # This should not raise an error until open() is called
    device = Device("/unknown")
    assert str(device.filename) == "/unknown"
    assert device.filename.name == "unknown"
    assert device.closed

    for name in (1, 1.1, True, [], {}, (), set()):
        with pytest.raises(TypeError):
            Device(name)


def test_device_creation_from_id():
    # This should not raise an error until open() is called
    device = Device.from_id(33)
    assert str(device.filename) == "/dev/gpiochip33"
    assert device.filename.name == "gpiochip33"
    assert device.closed


def test_device_open(chip):
    device = Device(chip.filename)
    assert chip.fobj is None
    assert device.closed
    device.open()
    assert not device.closed
    assert device.fileno() == chip.fd


def test_get_info(chip):
    device = Device(chip.filename)

    with pytest.raises(AttributeError):
        device.get_info()

    with device:
        info = device.get_info()
    assert info.name == chip.name.decode()
    assert info.label == chip.label.decode()
    assert len(info.lines) == chip.nb_lines
    l1 = info.lines[1]
    assert l1.flags == raw.LineFlag.USED | raw.LineFlag.OUTPUT
    assert l1.name == "Line1"
    assert l1.consumer == "another fellow"
    assert l1.attributes.flags == raw.LineFlag.ACTIVE_LOW
    assert isclose(l1.attributes.debounce_period, 99.123456)


def test_make_request(chip):
    nb_lines = chip.nb_lines
    with Device(chip.filename) as device:
        for blocking in (True, False):
            for request in (device[:], device.request()):
                request.blocking = blocking
                assert request.name == "linuxpy"
                assert all(lr.name == "linuxpy" for lr in request.line_requests)
                assert len(request.lines) == nb_lines
                assert request.min_line == 0
                assert request.max_line == nb_lines - 1
                assert len(request.line_requests) == ceil(nb_lines / 64)

            for request in (device[1], device.request([1])):
                assert len(request.lines) == 1
                assert len(request.line_requests) == 1
                assert request.min_line == 1
                assert request.max_line == 1
                assert request.lines == [1]

            lines = [1, 5, 10, 12]
            for request in (device[1, 5, 10:14:2], device.request(lines)):
                assert len(request.lines) == 4
                assert len(request.line_requests) == 1
                assert request.min_line == 1
                assert request.max_line == 12
                assert request.lines == lines

                # close the request to make sure it always succeeds
                request.close()


def test_get_value(chip):
    def assert_request(request):
        for values in (request[:], request.get_values()):
            assert len(values) == 9
            for i in range(1, 10):
                expected = 1 if i % 2 else 0
                assert values[i] == expected

        lines = [2, 3, 5, 7]
        for values in (request[2, 3:8:2], request.get_values(lines)):
            assert len(values) == len(lines)
            for i in lines:
                expected = 1 if i % 2 else 0
                assert values[i] == expected

        expected = {2: 0, 1: 1}
        assert request[1] == expected[1]
        assert request[2] == expected[2]
        assert request[1, 2] == expected
        assert request[1:3] == expected

        with pytest.raises(KeyError):
            request[0]

        with pytest.raises(KeyError):
            request[20]

        with pytest.raises(KeyError):
            request[-1]

    with Device(chip.filename) as device:
        with device[1:10] as request:
            assert_request(request)

        for blocking in (False, True):
            with device.request({"name": "me", "lines": list(range(1, 10))}, blocking=blocking) as request:
                assert_request(request)


def test_set_value(chip):
    with Device(chip.filename) as device:
        with device[1:10] as request:
            assert request[1, 2] == {2: 0, 1: 1}

            request.set_values({1: 0})
            assert request[1, 2] == {2: 0, 1: 0}

            request.set_values({2: 1, 1: 1})
            assert request[1, 2] == {2: 1, 1: 1}

            request[1] = 0
            assert request[1, 2] == {2: 1, 1: 0}

            request[2] = 1
            assert request[1, 2] == {2: 1, 1: 0}

            request[1, 2] = [1, 0]
            assert request[1, 2] == {2: 0, 1: 1}

            request[1:3] = [0, 1]
            assert request[1, 2] == {2: 1, 1: 0}

            request[:] = 9 * [1]
            assert request[:] == dict.fromkeys(range(1, 10), 1)

            request[:] = 0
            assert request[:] == dict.fromkeys(range(1, 10), 0)

            request[3, 4, 7:10] = 1, 0, 1, 0, 1
            assert request[3, 4, 7:10] == {3: 1, 4: 0, 7: 1, 8: 0, 9: 1}

            with pytest.raises(ValueError):
                request[1] = [0, 1]


def test_event_stream(chip):
    with Device(chip.filename) as device:
        line = 11
        with device[line] as request:
            line_request = request.line_requests[0]
            chip.trigger_event(line_request, line, LineEventId.RISING_EDGE, 55, 22, 1_999_999_000)
            chip.trigger_event(line_request, line, LineEventId.FALLING_EDGE, 57, 23, 2_999_999_000)
            for i, event in enumerate(request):
                assert event.line == line
                if not i:
                    assert isclose(event.timestamp, 1.999_999)
                    assert event.sequence == 55
                    assert event.line_sequence == 22
                    assert event.type == LineEventId.RISING_EDGE
                else:
                    assert isclose(event.timestamp, 2.999_999)
                    assert event.sequence == 57
                    assert event.line_sequence == 23
                    assert event.type == LineEventId.FALLING_EDGE
                if i > 0:
                    break


@pytest.mark.asyncio
async def test_async_event_stream(chip):
    with Device(chip.filename) as device:
        line = 11
        with device[line] as request:
            line_request = request.line_requests[0]
            chip.trigger_event(line_request, line, LineEventId.RISING_EDGE, 55, 22, 1_999_999_000)
            chip.trigger_event(line_request, line, LineEventId.FALLING_EDGE, 57, 23, 2_999_999_000)
            async with aclosing(request.__aiter__()) as stream:
                i = 0
                async for event in stream:
                    assert event.line == line
                    if not i:
                        assert isclose(event.timestamp, 1.999_999)
                        assert event.sequence == 55
                        assert event.line_sequence == 22
                        assert event.type == LineEventId.RISING_EDGE
                    else:
                        assert isclose(event.timestamp, 2.999_999)
                        assert event.sequence == 57
                        assert event.line_sequence == 23
                        assert event.type == LineEventId.FALLING_EDGE
                    i += 1
                    if i > 0:
                        break


sim_file = find_gpio_sim_file()


@pytest.mark.skipif(sim_file is None, reason="gpio-sim not prepared")
def test_sim_read_chip_info():
    with sim_file.open() as chip:
        info = device.get_chip_info(chip)
        assert "gpio-sim" in info.label
        assert info.lines == 16


@pytest.mark.skipif(sim_file is None, reason="gpio-sim not prepared")
def test_sim_device_open():
    device = Device(sim_file)
    assert device.closed
    device.open()
    assert not device.closed
    assert device.fileno() > 0


@pytest.mark.skipif(sim_file is None, reason="gpio-sim not prepared")
def test_sim_get_info():
    device = Device(sim_file)

    with pytest.raises(AttributeError):
        device.get_info()

    with device:
        info = device.get_info()
    assert info.name == sim_file.stem
    assert "gpio-sim" in info.label
    assert len(info.lines) == 16
    l0 = info.lines[0]
    assert l0.flags == raw.LineFlag.INPUT
    assert l0.name == "L-I0"
    assert l0.consumer == ""
    assert l0.line == 0
    assert l0.attributes.flags == 0
    assert l0.attributes.debounce_period is None

    l1 = info.lines[1]
    assert l1.flags == raw.LineFlag.INPUT
    assert l1.name == "L-I1"
    assert l1.consumer == ""
    assert l1.line == 1
    assert l1.attributes.flags == 0

    l2 = info.lines[2]
    assert l2.flags == raw.LineFlag.USED | raw.LineFlag.INPUT
    assert l2.name == "L-I2"
    assert l2.consumer == "L-I2-hog"
    assert l2.line == 2
    assert l2.attributes.flags == 0

    l3 = info.lines[3]
    assert l3.flags == raw.LineFlag.USED | raw.LineFlag.OUTPUT
    assert l3.name == "L-O0"
    assert l3.consumer == "L-O0-hog"
    assert l3.line == 3
    assert l3.attributes.flags == 0

    l4 = info.lines[4]
    assert l4.flags == raw.LineFlag.USED | raw.LineFlag.OUTPUT
    assert l4.name == "L-O1"
    assert l4.consumer == "L-O1-hog"
    assert l4.line == 4
    assert l4.attributes.flags == 0


@pytest.mark.skipif(sim_file is None, reason="gpio-sim not prepared")
def test_sim_make_request():
    nb_lines = 16
    with Device(sim_file) as device:
        for blocking in (True, False):
            for request in (device[:], device.request()):
                assert len(request) == nb_lines
                request.blocking = blocking
                assert len(request.lines) == nb_lines
                assert request.min_line == 0
                assert request.max_line == nb_lines - 1
                assert len(request.line_requests) == ceil(nb_lines / 64)

            for request in (device[1], device.request([1])):
                assert len(request.lines) == 1
                assert len(request.line_requests) == 1
                assert request.min_line == 1
                assert request.max_line == 1
                assert request.lines == [1]

            lines = [1, 5, 10, 12]
            for request in (device[1, 5, 10:14:2], device.request(lines)):
                assert len(request.lines) == 4
                assert len(request.line_requests) == 1
                assert request.min_line == 1
                assert request.max_line == 12
                assert request.lines == lines

                # close the request to make sure it always succeeds
                request.close()

            config = {"name": "myself", "lines": [CLine(5, "output"), CLine(12, "output")]}
            with device.request(config) as request:
                info = device.get_info()
                l5 = info.lines[5]
                assert l5.flags == raw.LineFlag.USED | raw.LineFlag.OUTPUT
                assert l5.name == "L-O2"
                assert l5.consumer == "myself"
                assert l5.attributes.flags == 0

            # complex config
            config = [
                CLine(6, "output"),
                CLine(7, "input", edge="rising"),
                CLine(8, "output", clock="monotonic"),  # , bias="pull-up"),
            ]
            request = device.request(config)
            request.name = "linuxpy-tests"
            with request:
                info = device.get_info()
                l6 = info.lines[6]
                assert l6.flags == raw.LineFlag.USED | raw.LineFlag.OUTPUT
                assert l6.name == ""
                assert l6.consumer == request.name
                assert l6.attributes.flags == 0


@pytest.mark.skipif(sim_file is None, reason="gpio-sim not prepared")
def test_sim_get_value():
    def assert_request(request):
        for values in (request[:], request.get_values()):
            assert len(values) == 10
            for i in range(6, 16):
                expected = 0
                assert values[i] == expected

        lines = [6, 9, 11, 13]
        for values in (request[6, 9:14:2], request.get_values(lines)):
            assert len(values) == len(lines)
            for i in lines:
                expected = 0
                assert values[i] == expected

        assert request[6] == 0
        assert request[9] == 0
        assert request[6, 9] == {6: 0, 9: 0}
        assert request[9:14:2] == {9: 0, 11: 0, 13: 0}

        with pytest.raises(KeyError):
            request[0]

        with pytest.raises(KeyError):
            request[20]

        with pytest.raises(KeyError):
            request[-1]

    with Device(sim_file) as device:
        with device[6:16] as request:
            assert_request(request)

        with device.request({"name": "Me", "lines": list(range(6, 16))}) as request:
            assert_request(request)


@pytest.mark.skipif(sim_file is None, reason="gpio-sim not prepared")
def test_sim_set_value():
    with Device(sim_file) as device:
        with device.request([CLine(i, "output") for i in range(5, 14)]) as request:
            request.set_values({10: 1})
            assert request[10] == 1

            request.set_values({5: 0, 6: 1})
            assert request[5, 6] == {5: 0, 6: 1}

            request[9] = 1
            assert request[5, 6, 9] == {5: 0, 6: 1, 9: 1}

            request[11, 12] = [1, 0]
            assert request[11, 12] == {11: 1, 12: 0}

            request[9:12] = 0
            assert request[9:12] == {9: 0, 10: 0, 11: 0}

            request[:] = 9 * [1]
            assert request[:] == dict.fromkeys(range(5, 14), 1)

            request[:] = 0
            assert request[:] == dict.fromkeys(range(5, 14), 0)

            request[7, 8, 11:14] = 1, 0, 1, 0, 1
            assert request[7, 8, 11:14] == {7: 1, 8: 0, 11: 1, 12: 0, 13: 1}


@pytest.mark.skipif(sim_file is None, reason="gpio-sim not prepared")
def test_sim_line_config_event():
    def run():
        time.sleep(0.001)
        with Device(sim_file) as dev:
            with dev.request([5, 10, 15]):
                pass

    task = threading.Thread(target=run)
    task.start()

    with Device(sim_file) as device:
        names_req = {"L-O2", ""}
        lines_req = {5, 15}
        names_rel = set(names_req)
        lines_rel = set(lines_req)

        i = 0
        for event in device.info_stream(list(lines_req)):
            if i < 2:
                names_req.remove(event.name)
                lines_req.remove(event.line)
                assert event.flags == raw.LineFlag.USED | raw.LineFlag.INPUT
                assert event.type == raw.LineChangedType.REQUESTED
            else:
                names_rel.remove(event.name)
                lines_rel.remove(event.line)
                assert event.flags == raw.LineFlag.INPUT
                assert event.type == raw.LineChangedType.RELEASED

            assert event.attributes.flags == raw.LineFlag(0)
            assert event.attributes.indexes == []
            assert event.attributes.debounce_period is None
            i += 1
            if i == len(lines_req) + len(lines_rel):
                break

    with Device(sim_file) as device:
        with device.watching([5, 15]):
            stream = iter(device)
            before = time.monotonic()
            with device.request([5, 10, 15]):
                after = time.monotonic()
                names = {"L-O2", ""}
                lines = {5, 15}
                for _ in range(2):
                    event = next(stream)
                    # name and line must be in the sets for test to succeed
                    names.remove(event.name)
                    lines.remove(event.line)
                    assert event.flags == raw.LineFlag.USED | raw.LineFlag.INPUT
                    assert event.type == raw.LineChangedType.REQUESTED
                    assert before < event.timestamp < after
                    assert event.attributes.flags == raw.LineFlag(0)
                    assert event.attributes.indexes == []
                    assert event.attributes.debounce_period is None
                before = time.monotonic()
            after = time.monotonic()
            names = {"L-O2", ""}
            lines = {5, 15}
            for _ in range(2):
                event = next(stream)
                names.remove(event.name)
                lines.remove(event.line)
                assert event.flags == raw.LineFlag.INPUT
                assert event.type == raw.LineChangedType.RELEASED
                assert before < event.timestamp < after
                assert event.attributes.flags == raw.LineFlag(0)
                assert event.attributes.indexes == []
                assert event.attributes.debounce_period is None


@pytest.mark.asyncio
@pytest.mark.skipif(sim_file is None, reason="gpio-sim not prepared")
async def test_async_sim_line_config_event():
    async def run():
        await asyncio.sleep(0.001)
        with Device(sim_file) as dev:
            with dev.request([5, 10, 15]):
                pass

    asyncio.create_task(run())

    with Device(sim_file) as device:
        names_req = {"L-O2", ""}
        lines_req = {5, 15}
        names_rel = set(names_req)
        lines_rel = set(lines_req)

        i = 0
        async with aclosing(device.async_info_stream(list(lines_req))) as stream:
            async for event in stream:
                if i < 2:
                    names_req.remove(event.name)
                    lines_req.remove(event.line)
                    assert event.flags == raw.LineFlag.USED | raw.LineFlag.INPUT
                    assert event.type == raw.LineChangedType.REQUESTED
                else:
                    names_rel.remove(event.name)
                    lines_rel.remove(event.line)
                    assert event.flags == raw.LineFlag.INPUT
                    assert event.type == raw.LineChangedType.RELEASED

                assert event.attributes.flags == raw.LineFlag(0)
                assert event.attributes.indexes == []
                assert event.attributes.debounce_period is None
                i += 1
                if i == len(lines_req) + len(lines_rel):
                    break
