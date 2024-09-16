#
# This file is part of the linuxpy project
#
# Copyright (c) 2024 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import os
from contextlib import ExitStack, contextmanager
from inspect import isgenerator
from itertools import count
from math import ceil
from pathlib import Path
from unittest import mock

from ward import each, fixture, raises, test

from linuxpy.device import device_number
from linuxpy.gpio import raw
from linuxpy.gpio.device import Device, Request, expand_from_list, iter_devices, iter_gpio_files
from linuxpy.util import bit_indexes


def FD():
    return next(FD._FD)


FD._FD = count(1001, 2)


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
                request_fd = FD()
                arg.fd = request_fd
                self.requests[request_fd] = arg
        else:
            request = self.requests[fd]
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


@fixture
def emulate_gpiochip():
    with Hardware() as hardware:
        yield hardware


@test("expand list")
def _():
    assert [5] == expand_from_list(5, None, None)
    assert [5, 10] == expand_from_list((5, 10), None, None)
    assert list(range(100)) == expand_from_list(slice(100), 0, 100)
    assert list(range(10)) == expand_from_list(slice(10), 0, 100)


@test("device number")
def _(
    filename=each("/dev/gpiochip0", "/dev/gpiochip1", "/dev/gpiochip99"),
    expected=each(0, 1, 99),
):
    assert device_number(filename) == expected


@test("gpio files")
def _():
    with gpio_files(["/dev/gpiochip33", "/dev/gpiochip55"]) as expected_files:
        assert list(iter_gpio_files()) == expected_files


@test("device list")
def _():
    assert isgenerator(iter_devices())

    with gpio_files(["/dev/gpiochip33", "/dev/gpiochip55"]) as expected_files:
        devices = list(iter_devices())
        assert len(devices) == 2
        for device in devices:
            assert isinstance(device, Device)
        assert {device.filename for device in devices} == {Path(filename) for filename in expected_files}


@test("device creation")
def _():
    # This should not raise an error until open() is called
    device = Device("/unknown")
    assert str(device.filename) == "/unknown"
    assert device.filename.name == "unknown"
    assert device.closed

    for name in (1, 1.1, True, [], {}, (), set()):
        with raises(TypeError):
            Device(name)


@test("device creation from id")
def _():
    # This should not raise an error until open() is called
    device = Device.from_id(33)
    assert str(device.filename) == "/dev/gpiochip33"
    assert device.filename.name == "gpiochip33"
    assert device.closed


@test("device open")
def _(chip=emulate_gpiochip):
    device = Device(chip.filename)
    assert chip.fobj is None
    assert device.closed
    device.open()
    assert not device.closed
    assert device.fileno() == chip.fd


@test("get info")
def _(chip=emulate_gpiochip):
    device = Device(chip.filename)

    with raises(AttributeError):
        device.get_info()

    with device:
        info = device.get_info()
        assert info.name == chip.name.decode()
        assert info.label == chip.label.decode()


@test("make request")
def _(chip=emulate_gpiochip):
    nb_lines = chip.nb_lines
    with Device(chip.filename) as device:
        for request in (device[:], device.request(), Request(None, list(range(nb_lines)))):
            assert len(request.lines) == nb_lines
            assert request.min_line == 0
            assert request.max_line == nb_lines - 1
            assert len(request.line_requests) == ceil(nb_lines / 64)

        for request in (device[1], device.request([1]), Request(None, [1])):
            assert len(request.lines) == 1
            assert len(request.line_requests) == 1
            assert request.min_line == 1
            assert request.max_line == 1
            assert request.lines == [1]

        lines = [1, 5, 10, 12]
        for request in (device[1, 5, 10:14:2], device.request(lines), Request(None, lines)):
            assert len(request.lines) == 4
            assert len(request.line_requests) == 1
            assert request.min_line == 1
            assert request.max_line == 12
            assert request.lines == lines


@test("get value")
def _(chip=emulate_gpiochip):
    with Device(chip.filename) as device:
        with device[1:10] as request:
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

            with raises(KeyError):
                request[0]

            with raises(KeyError):
                request[20]

            with raises(KeyError):
                request[-1]


@test("set value")
def _(chip=emulate_gpiochip):
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
            assert request[:] == {i: 1 for i in range(1, 10)}
