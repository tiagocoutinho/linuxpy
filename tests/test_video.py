#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import os
import subprocess
from contextlib import ExitStack, contextmanager
from errno import EINVAL
from functools import cache
from inspect import isgenerator
from math import isclose
from pathlib import Path
from random import randint
from unittest import mock

from ward import each, fixture, raises, skip, test

try:
    import numpy
except ImportError:
    numpy = None

from linuxpy.device import device_number
from linuxpy.video import raw
from linuxpy.video.device import (
    BufferType,
    Capability,
    ControlClass,
    Device,
    Memory,
    PixelFormat,
    VideoCapture,
    VideoOutput,
    iter_devices,
    iter_video_files,
)


@contextmanager
def video_files(paths=("/dev/video99")):
    with mock.patch("linuxpy.device.pathlib.Path.glob") as glob:
        expected_files = list(paths)
        glob.return_value = expected_files
        with mock.patch("linuxpy.device.pathlib.Path.is_char_device") as is_char_device:
            is_char_device.return_value = True
            with mock.patch("linuxpy.device.os.access") as access:
                access.return_value = os.R_OK | os.W_OK
                yield paths


class MemoryMap:
    def __init__(self, hardware):
        self.hardware = hardware

    def __getitem__(self, item):
        assert item.start is None
        assert item.stop == len(self.hardware.frame)
        assert item.step is None
        return self.hardware.frame

    def close(self):
        pass


class Hardware:
    def __init__(self, filename="/dev/video39"):
        self.filename = filename
        self.fd = None
        self.fobj = None
        self.input0_name = b"my camera"
        self.driver = b"mock"
        self.card = b"mock camera"
        self.bus_info = b"mock:usb"
        self.version = 5 << 16 | 4 << 8 | 12
        self.version_str = "5.4.12"
        self.video_capture_state = "OFF"
        self.blocking = None
        self.frame = 640 * 480 * 3 * b"\x01"

    def __enter__(self):
        self.stack = ExitStack()
        ioctl = mock.patch("linuxpy.ioctl.fcntl.ioctl", self.ioctl)
        opener = mock.patch("linuxpy.io.open", self.open)
        mmap = mock.patch("linuxpy.video.device.mmap.mmap", self.mmap)
        select = mock.patch("linuxpy.io.IO.select", self.select)
        blocking = mock.patch("linuxpy.device.os.get_blocking", self.get_blocking)
        self.stack.enter_context(ioctl)
        self.stack.enter_context(opener)
        self.stack.enter_context(mmap)
        self.stack.enter_context(select)
        self.stack.enter_context(blocking)
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.stack.close()

    def open(self, filename, mode, buffering=-1, opener=None):
        self.fd = randint(100, 1000)
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

    def ioctl(self, fd, ioc, arg):  # noqa: C901
        assert self.fd == fd
        if isinstance(arg, raw.v4l2_input):
            if arg.index > 0:
                raise OSError(EINVAL, "ups!")
            arg.name = self.input0_name
            arg.type = raw.InputType.CAMERA
        elif isinstance(arg, raw.v4l2_query_ext_ctrl):
            if arg.index > 0:
                raise OSError(EINVAL, "ups!")
            arg.name = b"brightness"
            arg.type = raw.CtrlType.INTEGER
            arg.id = 9963776
        elif isinstance(arg, raw.v4l2_capability):
            arg.driver = self.driver
            arg.card = self.card
            arg.bus_info = self.bus_info
            arg.version = self.version
            arg.capabilities = raw.Capability.STREAMING | raw.Capability.VIDEO_CAPTURE
        elif isinstance(arg, raw.v4l2_format):
            if ioc == raw.IOC.G_FMT:
                arg.fmt.pix.width = 640
                arg.fmt.pix.height = 480
                arg.fmt.pix.pixelformat = raw.PixelFormat.RGB24
        elif isinstance(arg, raw.v4l2_buffer):
            if ioc == raw.IOC.QUERYBUF:
                pass
            elif ioc == raw.IOC.DQBUF:
                arg.index = 0
                arg.bytesused = len(self.frame)
                arg.sequence = 123
                arg.timestamp.secs = 123
                arg.timestamp.usecs = 456789
        elif ioc == raw.IOC.STREAMON:
            assert arg.value == raw.BufType.VIDEO_CAPTURE
            self.video_capture_state = "ON"
        elif ioc == raw.IOC.STREAMOFF:
            assert arg.value == raw.BufType.VIDEO_CAPTURE
            self.video_capture_state = "OFF"
        return 0

    def mmap(self, fd, length, offset):
        assert self.fd == fd
        return MemoryMap(self)

    def select(self, readers, writers, other, timeout=None):
        assert readers[0].fileno() == self.fd
        return readers, writers, other


@fixture
def hardware():
    with Hardware() as hardware:
        yield hardware


def assert_frame(frame, camera):
    """Helper to compare frame with hardware frame"""
    assert frame.data == camera.frame
    assert frame.width == 640
    assert frame.height == 480
    assert frame.pixel_format == PixelFormat.RGB24
    assert frame.index == 0
    assert frame.frame_nb == 123
    assert frame.type == BufferType.VIDEO_CAPTURE
    assert isclose(frame.timestamp, 123.456789)
    assert bytes(frame) == camera.frame
    assert len(frame) == len(camera.frame)
    assert frame.nbytes == len(camera.frame)
    if numpy:
        assert numpy.all(frame.array == numpy.frombuffer(camera.frame, dtype="u1"))


@test("device number")
def _(
    filename=each("/dev/video0", "/dev/video1", "/dev/video999"),
    expected=each(0, 1, 999),
):
    assert device_number(filename) == expected


@test("video files")
def _():
    with video_files(["/dev/video33", "/dev/video55"]) as expected_files:
        assert list(iter_video_files()) == expected_files


@test("device list")
def _():
    assert isgenerator(iter_devices())

    with video_files(["/dev/video33", "/dev/video55"]) as expected_files:
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
    assert str(device.filename) == "/dev/video33"
    assert device.filename.name == "video33"
    assert device.closed


@test("device open")
def _(camera=hardware):
    device = Device(camera.filename)
    assert camera.fobj is None
    assert device.closed
    assert device.info is None
    device.open()
    assert not device.closed
    assert device.info is not None
    assert device.fileno() == camera.fd


@test("device close")
def _(camera=hardware):
    device = Device(camera.filename)
    assert camera.fobj is None
    assert device.closed
    assert device.info is None
    device.open()
    assert not device.closed
    assert device.info is not None
    assert device.fileno() == camera.fd
    device.close()
    assert device.closed


@test("device info")
def _(camera=hardware):
    device = Device(camera.filename)
    device.opener = camera.open
    assert device.info is None
    device.open()
    assert device.info.driver == camera.driver.decode()
    assert device.info.bus_info == camera.bus_info.decode()
    assert device.info.bus_info == camera.bus_info.decode()
    assert device.info.version == camera.version_str


@test("device repr")
def _(camera=hardware):
    device = Device(camera.filename)
    assert repr(device) == f"<Device name={camera.filename}, closed=True>"
    device.open()
    assert repr(device) == f"<Device name={camera.filename}, closed=False>"


@test("create video capture")
def _(camera=hardware):
    device = Device(camera.filename)
    video_capture = VideoCapture(device)
    assert video_capture.device is device


@test("synch device acquisition")
def _(camera=hardware):
    with Device(camera.filename) as device:
        stream = iter(device)
        frame = next(stream)
        assert_frame(frame, camera)


@test("synch video capture acquisition")
def _(camera=hardware):
    with Device(camera.filename) as device:
        with VideoCapture(device) as video_capture:
            for frame in video_capture:
                assert_frame(frame, camera)
                break


V4L2_LOOPBACK_TEST_DEVICE = Path("/dev/video199")


@cache
def is_v4l2loopback_installed():
    result = subprocess.run("lsmod", capture_output=True, check=False, timeout=1)
    return result.returncode == 0 and b"v4l2loopback" in result.stdout


def is_v4l2looback_prepared():
    return V4L2_LOOPBACK_TEST_DEVICE.exists()


for output_type in (None, Capability.STREAMING, Capability.READWRITE):
    oname = "auto" if output_type is None else output_type.name
    for input_type in (None, Capability.STREAMING, Capability.READWRITE):
        iname = "auto" if input_type is None else input_type.name

        @skip(when=not is_v4l2looback_prepared(), reason="v4l2loopback is not prepared")
        @skip(when=not is_v4l2loopback_installed(), reason="v4l2loopback is not installed")
        @test(f"output({oname}) and capture({iname}) with v4l2loopback")
        def _(sink=output_type, source=input_type):
            with Device(V4L2_LOOPBACK_TEST_DEVICE) as outp, Device(V4L2_LOOPBACK_TEST_DEVICE) as inp:
                assert outp.info.card == "Loopback 199"
                assert Capability.STREAMING in outp.info.capabilities
                assert Capability.VIDEO_OUTPUT in outp.info.capabilities

                width, height, pixel_format = 320, 240, PixelFormat.RGB24
                size = width * height * 3
                output = VideoOutput(outp, sink=sink)
                output.set_format(width, height, pixel_format)
                fmt = output.get_format()
                assert fmt.width == width
                assert fmt.height == height
                assert fmt.pixel_format == pixel_format

                with output:
                    assert inp.info.card == "Loopback 199"
                    assert Capability.STREAMING in inp.info.capabilities
                    assert Capability.VIDEO_OUTPUT in inp.info.capabilities

                    with VideoCapture(inp, source=source) as capture:
                        fmt = capture.get_format()
                        assert fmt.width == width
                        assert fmt.height == height
                        assert fmt.pixel_format == pixel_format

                        data = os.urandom(size)
                        output.write(data)

                        stream = iter(capture)
                        frame = next(stream)
                        assert frame.data == data
                        assert frame.nbytes == size
                        assert frame.memory == Memory.MMAP if source is None else source
                        assert frame.pixel_format == pixel_format


for output_type in (None, Capability.STREAMING, Capability.READWRITE):
    oname = "auto" if output_type is None else output_type.name
    for input_type in (None, Capability.STREAMING, Capability.READWRITE):
        iname = "auto" if input_type is None else input_type.name

        @skip(when=not is_v4l2looback_prepared(), reason="v4l2loopback is not prepared")
        @skip(when=not is_v4l2loopback_installed(), reason="v4l2loopback is not installed")
        @test(f"output({oname}) and async capture({iname}) with v4l2loopback")
        async def _(sink=output_type, source=input_type):
            with Device(V4L2_LOOPBACK_TEST_DEVICE) as outp, Device(V4L2_LOOPBACK_TEST_DEVICE) as inp:
                assert outp.info.card == "Loopback 199"
                assert Capability.STREAMING in outp.info.capabilities
                assert Capability.VIDEO_OUTPUT in outp.info.capabilities

                width, height, pixel_format = 320, 240, PixelFormat.RGB24
                size = width * height * 3
                output = VideoOutput(outp, sink=sink)
                output.set_format(width, height, pixel_format)
                fmt = output.get_format()
                assert fmt.width == width
                assert fmt.height == height
                assert fmt.pixel_format == pixel_format

                with output:
                    assert inp.info.card == "Loopback 199"
                    assert Capability.STREAMING in inp.info.capabilities
                    assert Capability.VIDEO_OUTPUT in inp.info.capabilities

                    with VideoCapture(inp, source=source) as capture:
                        fmt = capture.get_format()
                        assert fmt.width == width
                        assert fmt.height == height
                        assert fmt.pixel_format == pixel_format

                        data = os.urandom(size)
                        output.write(data)

                        async for frame in capture:
                            assert frame.data == data
                            assert frame.nbytes == size
                            assert frame.memory == Memory.MMAP if source is None else source
                            assert frame.pixel_format == pixel_format
                            break


@skip(when=not is_v4l2looback_prepared(), reason="v4l2loopback is not prepared")
@skip(when=not is_v4l2loopback_installed(), reason="v4l2loopback is not installed")
@test("controls with v4l2loopback")
def _():
    with Device(V4L2_LOOPBACK_TEST_DEVICE) as device:
        controls = device.controls
        assert controls.keep_format is controls["keep_format"]
        current_value = controls.keep_format.value
        assert current_value in {True, False}
        try:
            controls.keep_format.value = not current_value
            assert controls.keep_format.value == (not current_value)
        finally:
            controls.keep_format.value = current_value

        with raises(AttributeError):
            _ = controls.unknown_field

        assert ControlClass.USER in controls.used_classes()
        assert controls.keep_format in controls.with_class("user")
        assert controls.keep_format in controls.with_class(ControlClass.USER)

        assert "<BooleanControl keep_format" in repr(controls.keep_format)
        with raises(ValueError):
            _ = list(controls.with_class("unknown class"))

        with raises(TypeError):
            _ = list(controls.with_class(55))
