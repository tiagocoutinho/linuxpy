#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import os
from contextlib import ExitStack, contextmanager
from errno import EINVAL, ENODATA
from inspect import isgenerator
from math import isclose
from pathlib import Path
from random import randint
from unittest import mock

import pytest

try:
    import numpy
except ImportError:
    numpy = None

from linuxpy.device import device_number
from linuxpy.io import GeventIO, fopen
from linuxpy.video import raw
from linuxpy.video.device import (
    BufferFlag,
    BufferType,
    Capability,
    ControlClass,
    ControlType,
    Device,
    EventControlChange,
    EventReader,
    EventSubscriptionFlag,
    EventType,
    InputCapabilities,
    Memory,
    MetaFormat,
    PixelFormat,
    Priority,
    SelectionTarget,
    StandardID,
    V4L2Error,
    VideoCapture,
    VideoOutput,
    iter_devices,
    iter_video_capture_devices,
    iter_video_capture_files,
    iter_video_files,
    iter_video_output_devices,
    iter_video_output_files,
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
        self.fps_capture = 10
        self.fps_output = 20
        self.brightness = 55
        self.contrast = 12
        self.edid = bytes(range(0, 256))  # Its not valid edid, just random data for testing

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
        # assert self.fd == fd
        self.ioctl_ioc = ioc
        self.ioctl_arg = arg
        if isinstance(arg, raw.v4l2_input):
            if arg.index > 0:
                raise OSError(EINVAL, "ups!")
            arg.name = self.input0_name
            arg.type = raw.InputType.CAMERA
        elif isinstance(arg, raw.v4l2_output):
            if arg.index > 0:
                raise OSError(EINVAL, "ups!")
            arg.name = self.input0_name
            arg.type = raw.OutputType.ANALOG
        elif isinstance(arg, raw.v4l2_standard):
            raise OSError(EINVAL, "ups!")
        elif isinstance(arg, raw.v4l2_query_ext_ctrl):
            if arg.index == 0:
                arg.name = b"brightness"
                arg.type = raw.CtrlType.INTEGER
                arg.id = 9963776
                arg.minimum = 10
                arg.maximum = 127
                arg.step = 1
                arg.default_value = 64
            elif arg.index == 1:
                arg.name = b"contrast"
                arg.type = raw.CtrlType.INTEGER
                arg.id = 9963777
                arg.flags = raw.ControlFlag.READ_ONLY
            elif arg.index == 2:
                arg.name = b"white_balance_automatic"
                arg.type = raw.CtrlType.BOOLEAN
                arg.id = 9963788
                arg.flags = raw.ControlFlag.DISABLED
            else:
                raise OSError(EINVAL, "ups!")
        elif isinstance(arg, raw.v4l2_capability):
            arg.driver = self.driver
            arg.card = self.card
            arg.bus_info = self.bus_info
            arg.version = self.version
            arg.capabilities = raw.Capability.STREAMING | raw.Capability.VIDEO_CAPTURE
            arg.device_caps = raw.Capability.STREAMING | raw.Capability.VIDEO_CAPTURE
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
        elif isinstance(arg, raw.v4l2_edid):
            # Our mock doesn't support pad != 0 at the moment
            assert arg.pad == 0
            # Documentation for VIDIOC_G_EDID states that this is maximum value defined by the standard
            assert arg.blocks <= 256
            if ioc == raw.IOC.S_EDID:
                assert arg.start_block == 0
                self.edid = arg.edid[: arg.blocks * 128]
            elif ioc == raw.IOC.G_EDID:
                if arg.blocks == 0 and arg.start_block == 0:
                    arg.blocks = len(self.edid) // 128
                else:
                    blocks_to_copy = len(self.edid) // 128 - arg.start_block
                    if blocks_to_copy == 0:
                        raise OSError(ENODATA, "ups!")
                    blocks_to_copy = min(blocks_to_copy, arg.blocks)
                    for i in range(blocks_to_copy * 128):
                        arg.edid[i] = self.edid[arg.start_block * 128 + i]
                    arg.blocks = blocks_to_copy
            else:
                raise OSError(EINVAL, "ups!")
        elif ioc == raw.IOC.STREAMON:
            assert arg.value == raw.BufType.VIDEO_CAPTURE
            self.video_capture_state = "ON"
        elif ioc == raw.IOC.STREAMOFF:
            assert arg.value == raw.BufType.VIDEO_CAPTURE
            self.video_capture_state = "OFF"
        elif ioc == raw.IOC.CROPCAP:
            raise OSError(EINVAL, "ups!")
        elif ioc == raw.IOC.G_PARM:
            if arg.type == raw.BufType.VIDEO_CAPTURE:
                arg.parm.capture.timeperframe.numerator = 1
                arg.parm.capture.timeperframe.denominator = self.fps_capture
            elif arg.type == raw.BufType.VIDEO_OUTPUT:
                arg.parm.output.timeperframe.numerator = 1
                arg.parm.output.timeperframe.denominator = self.fps_output
        elif ioc == raw.IOC.S_PARM:
            if arg.type == raw.BufType.VIDEO_CAPTURE:
                assert arg.parm.capture.timeperframe.numerator == 1
                self.fps_capture = arg.parm.capture.timeperframe.denominator
            elif arg.type == raw.BufType.VIDEO_OUTPUT:
                assert arg.parm.output.timeperframe.numerator == 1
                self.fps_output = arg.parm.output.timeperframe.denominator
        elif ioc == raw.IOC.G_CTRL:
            if arg.id == 9963776:
                arg.value = self.brightness
            elif arg.id == 9963777:
                arg.value = self.contrast
            elif arg.id == 9963788:
                arg.value = 0
            else:
                raise OSError(EINVAL, "ups!")
        elif ioc == raw.IOC.S_CTRL:
            if arg.id == 9963776:
                self.brightness = arg.value
            elif arg.id == 9963777:
                self.contrast = arg.value
            else:
                raise OSError(EINVAL, "ups!")
        elif ioc == raw.IOC.G_EXT_CTRLS:
            for i in range(arg.count):
                ctrl = arg.controls[i]
                if ctrl.id == 9963776:
                    ctrl.value = self.brightness
                elif ctrl.id == 9963777:
                    ctrl.value = self.contrast
                elif ctrl.id == 9963788:
                    ctrl.value = 0
                else:
                    raise OSError(EINVAL, "ups!")
        elif ioc == raw.IOC.S_EXT_CTRLS:
            for i in range(arg.count):
                ctrl = arg.controls[i]
                if ctrl.id == 9963776:
                    self.brightness = ctrl.value
                elif ctrl.id == 9963777:
                    self.contrast = ctrl.value
                else:
                    raise OSError(EINVAL, "ups!")
        return 0

    def mmap(self, fd, length, offset):
        assert self.fd == fd
        return MemoryMap(self)

    def select(self, readers, writers, other, timeout=None):
        assert readers[0].fileno() == self.fd
        return readers, writers, other


@pytest.fixture
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


@pytest.mark.parametrize("filename, expected", [("/dev/video0", 0), ("/dev/video1", 1), ("/dev/video999", 999)])
def test_device_number(filename, expected):
    assert device_number(filename) == expected


def test_video_files():
    with video_files(["/dev/video33", "/dev/video55"]) as expected_files:
        assert list(iter_video_files()) == expected_files


def test_device_list():
    assert isgenerator(iter_devices())

    with video_files(["/dev/video33", "/dev/video55"]) as expected_files:
        devices = list(iter_devices())
        assert len(devices) == 2
        for device in devices:
            assert isinstance(device, Device)
        assert {device.filename for device in devices} == {Path(filename) for filename in expected_files}


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
    assert str(device.filename) == "/dev/video33"
    assert device.filename.name == "video33"
    assert device.closed


def test_device_open(hardware):
    device = Device(hardware.filename)
    assert hardware.fobj is None
    assert device.closed
    assert device.info is None
    device.open()
    assert not device.closed
    assert device.info is not None
    assert device.fileno() == hardware.fd


def test_device_close(hardware):
    device = Device(hardware.filename)
    assert hardware.fobj is None
    assert device.closed
    assert device.info is None
    device.open()
    assert not device.closed
    assert device.info is not None
    assert device.fileno() == hardware.fd
    device.close()
    assert device.closed


def test_device_info(hardware):
    device = Device(hardware.filename)
    device.opener = hardware.open
    assert device.info is None
    device.open()
    assert device.info.driver == hardware.driver.decode()
    assert device.info.bus_info == hardware.bus_info.decode()
    assert device.info.bus_info == hardware.bus_info.decode()
    assert device.info.version == hardware.version_str


def test_set_format(hardware):
    device = Device(hardware.filename)
    with device:
        device.set_format(BufferType.VIDEO_CAPTURE, 7, 5, "pRCC")
    assert hardware.ioctl_ioc == raw.IOC.S_FMT
    assert hardware.ioctl_arg.fmt.pix.height == 5
    assert hardware.ioctl_arg.fmt.pix.width == 7
    assert hardware.ioctl_arg.fmt.pix.pixelformat == PixelFormat.SRGGB12P


def test_controls(hardware):
    with Device(hardware.filename) as device:
        controls = device.controls
        assert len(controls) == 3
        brightness = controls["brightness"]
        assert controls.brightness is brightness
        contrast = controls["contrast"]
        white_balance_automatic = controls["white_balance_automatic"]

        assert brightness.value == hardware.brightness
        assert brightness.minimum == 10
        assert brightness.maximum == 127
        assert brightness.step == 1

        brightness.value = 123
        assert brightness.value == 123
        assert hardware.brightness == 123

        brightness.increase(2)
        assert brightness.value == 125
        assert hardware.brightness == 125

        brightness.decrease(20)
        assert brightness.value == 105
        assert hardware.brightness == 105

        brightness.set_to_default()
        assert brightness.value == brightness.default
        assert hardware.brightness == brightness.default

        brightness.set_to_minimum()
        assert brightness.value == brightness.minimum

        brightness.set_to_maximum()
        assert brightness.value == brightness.maximum

        brightness.value = 128
        assert brightness.value == brightness.maximum
        brightness.value = 1
        assert brightness.value == brightness.minimum

        brightness.clipping = False
        with pytest.raises(ValueError):
            brightness.value = 128
        with pytest.raises(ValueError):
            brightness.value = 0
        brightness.clipping = True
        brightness.value = 128
        assert brightness.value == brightness.maximum
        brightness.value = 1
        assert brightness.value == brightness.minimum

        controls.set_clipping(False)
        assert brightness.clipping is False
        assert contrast.clipping is False
        controls.set_clipping(True)
        assert brightness.clipping is True
        assert contrast.clipping is True

        brightness.value = "122"
        assert brightness.value == 122
        assert hardware.brightness == 122

        brightness.value = True
        assert brightness.value == brightness.minimum
        assert hardware.brightness == brightness.minimum

        for value in (device, {}, [], "bla"):
            with pytest.raises(ValueError):
                brightness.value = value

        assert contrast.value == hardware.contrast
        with pytest.raises(AttributeError):
            contrast.value = 12

        white_balance_automatic = controls["white_balance_automatic"]
        assert white_balance_automatic.value is False
        with pytest.raises(AttributeError):
            white_balance_automatic.value = True


def test_get_fps(hardware):
    with Device(hardware.filename) as device:
        fps = device.get_fps(BufferType.VIDEO_CAPTURE)
        assert isclose(fps, 10)

        fps = device.get_fps(BufferType.VIDEO_OUTPUT)
        assert isclose(fps, 20)

        with pytest.raises(ValueError):
            device.get_fps(BufferType.VBI_CAPTURE)


def test_set_fps(hardware):
    with Device(hardware.filename) as device:
        device.set_fps(BufferType.VIDEO_CAPTURE, 35)
        fps = device.get_fps(BufferType.VIDEO_CAPTURE)
        assert isclose(fps, 35)

        device.set_fps(BufferType.VIDEO_OUTPUT, 5)
        fps = device.get_fps(BufferType.VIDEO_OUTPUT)
        assert isclose(fps, 5)

        with pytest.raises(ValueError):
            device.set_fps(BufferType.VBI_CAPTURE, 10)


def test_device_repr(hardware):
    device = Device(hardware.filename)
    assert repr(device) == f"<Device name={hardware.filename}, closed=True>"
    device.open()
    assert repr(device) == f"<Device name={hardware.filename}, closed=False>"


def test_create_video_capture(hardware):
    device = Device(hardware.filename)
    video_capture = VideoCapture(device)
    assert video_capture.device is device


def test_synch_device_acquisition(hardware):
    with Device(hardware.filename) as device:
        stream = iter(device)
        frame = next(stream)
        assert_frame(frame, hardware)


def test_synch_video_capture_acquisition(hardware):
    with Device(hardware.filename) as device:
        with VideoCapture(device) as video_capture:
            for frame in video_capture:
                assert_frame(frame, hardware)
                break


def test_get_edid(hardware):
    with Device(hardware.filename) as device:
        edid = device.get_edid()
        assert len(edid) == 256
        assert edid == bytes(range(0, 256))


def test_clear_edid(hardware):
    with Device(hardware.filename) as device:
        device.clear_edid()
        edid = device.get_edid()
        assert len(edid) == 0


def test_set_edid(hardware):
    with Device(hardware.filename) as device:
        # Generate some random edid with 3 blocks
        expected_edid = bytes(range(255, -1, -1)) + bytes(range(255, -1, -2))
        device.set_edid(expected_edid)
        edid = device.get_edid()
        assert len(edid) == 128 * 3
        assert edid == expected_edid

        with pytest.raises(ValueError):
            # Fail if edid length is not multiple of 128
            device.set_edid(bytes(range(0, 100)))


VIVID_TEST_DEVICES = [Path(f"/dev/video{i}") for i in range(190, 194)]
VIVID_CAPTURE_DEVICE, VIVID_OUTPUT_DEVICE, VIVID_META_CAPTURE_DEVICE, VIVID_META_OUTPUT_DEVICE = VIVID_TEST_DEVICES


def is_vivid_prepared():
    return all(path.exists() for path in VIVID_TEST_DEVICES)


vivid_only = pytest.mark.skipif(not is_vivid_prepared(), reason="vivid is not prepared")


@vivid_only
def test_list_vivid_files():
    video_files = list(iter_video_files())
    for video_file in VIVID_TEST_DEVICES:
        assert video_file in video_files


@vivid_only
def test_list_vivid_capture_files():
    video_files = list(iter_video_capture_files())
    assert VIVID_CAPTURE_DEVICE in video_files
    for video_file in VIVID_TEST_DEVICES[1:]:
        assert video_file not in video_files


@vivid_only
def test_list_vivid_output_files():
    video_files = list(iter_video_output_files())
    assert VIVID_OUTPUT_DEVICE in video_files
    assert VIVID_CAPTURE_DEVICE not in video_files
    for video_file in VIVID_TEST_DEVICES[2:]:
        assert video_file not in video_files


@vivid_only
def test_list_vivid_devices():
    devices = list(iter_devices())
    device_names = [dev.filename for dev in devices]
    for video_file in VIVID_TEST_DEVICES:
        assert video_file in device_names


@vivid_only
def test_list_vivid_capture_devices():
    devices = list(iter_video_capture_devices())
    device_names = [dev.filename for dev in devices]
    assert VIVID_CAPTURE_DEVICE in device_names
    for video_file in VIVID_TEST_DEVICES[1:]:
        assert video_file not in device_names


@vivid_only
def test_list_vivid_output_devices():
    devices = list(iter_video_output_devices())
    device_names = [dev.filename for dev in devices]
    assert VIVID_OUTPUT_DEVICE in device_names
    assert VIVID_CAPTURE_DEVICE not in device_names
    for video_file in VIVID_TEST_DEVICES[2:]:
        assert video_file not in device_names


@vivid_only
def test_controls_with_vivid():
    with Device(VIVID_CAPTURE_DEVICE) as device:
        device.set_input(0)

        controls = device.controls

        # Brightness
        brightness = controls.brightness
        assert brightness is controls["brightness"]
        current_value = brightness.value
        assert brightness.minimum <= current_value <= brightness.maximum
        try:
            brightness.value = 100
            assert brightness.value == 100
        finally:
            brightness.value = current_value

        with pytest.raises(AttributeError):
            _ = controls.unknown_field

        assert ControlClass.USER in {ctrl.id - 1 for ctrl in controls.used_classes()}
        assert brightness in controls.with_class("user")
        assert brightness in controls.with_class(ControlClass.USER)

        assert "<IntegerControl brightness" in repr(brightness)

        # I64
        integer_64_bits = controls.integer_64_bits
        assert integer_64_bits is controls["integer_64_bits"]
        value = randint(integer_64_bits.minimum, integer_64_bits.maximum)
        controls.integer_64_bits.value = value
        assert integer_64_bits.value == value

        assert "<Integer64Control integer_64_bits" in repr(integer_64_bits)

        # boolean
        boolean = controls.boolean
        assert boolean is controls["boolean"]
        assert boolean.value in (True, False)
        boolean.value = False
        assert boolean.value is False
        boolean.value = True
        assert boolean.value is True
        trues = ["true", "1", "yes", "on", "enable", True, 1, [1], {1: 2}, (1,)]
        falses = ["false", "0", "no", "off", "disable", False, 0, [], {}, (), None]
        interleaved = (value for pair in zip(trues, falses, strict=False) for value in pair)
        for i, value in enumerate(interleaved):
            expected = not bool(i % 2)
            boolean.value = value
            assert boolean.value is expected

        # menu
        menu = controls.menu
        assert menu is controls["menu"]
        assert menu.type == ControlType.MENU
        assert menu[1] == menu.data[1]

        menu.value = 1
        assert menu.value == 1

        with pytest.raises(OSError):
            menu.value = 0

        # string
        assert controls.string is controls["string"]
        current_value = controls.string.value
        try:
            controls.string.value = "hell"
            assert controls.string.value == "hell"
        finally:
            controls.string.value = current_value

        assert "<CompoundControl string flags=has_payload>" in repr(controls.string)

        # 2 element array
        assert controls.s32_2_element_array is controls["s32_2_element_array"]
        current_value = controls.s32_2_element_array.value
        try:
            controls.s32_2_element_array.value = [5, -5]
            assert controls.s32_2_element_array.value[:] == [5, -5]
        finally:
            controls.s32_2_element_array.value = current_value

        assert controls.s32_2_element_array.default[:] == [2, 2]

        assert "<CompoundControl s32_2_element_array flags=has_payload>" in repr(controls.s32_2_element_array)

        # matrix 8x16
        value = [list(range(i + 16, i + 16 + 8)) for i in range(16)]
        controls.u16_8x16_matrix.value = value
        result = [row[:] for row in controls.u16_8x16_matrix.value]
        assert value == result

        # struct
        assert controls.area is controls["area"]
        area = controls.area.value
        assert isinstance(area, raw.v4l2_area)
        width, height = randint(10, 1000), randint(10, 1000)
        controls.area.value = raw.v4l2_area(width, height)
        area = controls.area.value
        assert area.width == width
        assert area.height == height

        # button
        controls.button.push()

        # Unknown
        with pytest.raises(KeyError):
            _ = list(controls.with_class("unknown class"))

        with pytest.raises(ValueError):
            _ = list(controls.with_class(55))


@vivid_only
def test_info_with_vivid():
    with Device(VIVID_CAPTURE_DEVICE) as capture_dev:
        dev_caps = capture_dev.info.device_capabilities
        assert Capability.VIDEO_CAPTURE in dev_caps
        assert Capability.STREAMING in dev_caps
        assert Capability.READWRITE in dev_caps
        assert Capability.VIDEO_OUTPUT not in dev_caps
        assert Capability.META_CAPTURE not in dev_caps

        text = repr(capture_dev.info)
        assert "driver = " in text

        capture_dev.set_input(0)

        assert len(capture_dev.info.frame_sizes) > 10
        assert len(capture_dev.info.formats) > 10

        inputs = capture_dev.info.inputs
        assert len(inputs) > 0
        outputs = capture_dev.info.outputs
        assert len(outputs) == 0

        crop = capture_dev.info.crop_capabilities
        assert not crop
        for inp in inputs:
            capture_dev.set_input(inp.index)
            video_standards = capture_dev.info.video_standards
            if InputCapabilities.STD in inp.capabilities:
                assert video_standards
            else:
                assert not video_standards

    with Device(VIVID_OUTPUT_DEVICE) as output_dev:
        crop = output_dev.info.crop_capabilities
        assert crop
        assert BufferType.VIDEO_OUTPUT in crop

        dev_caps = output_dev.info.device_capabilities
        assert Capability.VIDEO_OUTPUT in dev_caps
        assert Capability.STREAMING in dev_caps
        assert Capability.READWRITE in dev_caps
        assert Capability.VIDEO_CAPTURE not in dev_caps
        assert Capability.META_CAPTURE not in dev_caps

        text = repr(output_dev.info)
        assert "driver = " in text

        assert len(output_dev.info.frame_sizes) == 0
        assert len(output_dev.info.formats) > 10

        inputs = output_dev.info.inputs
        assert len(inputs) == 0

        outputs = output_dev.info.outputs
        assert len(outputs) > 0

    with Device(VIVID_META_CAPTURE_DEVICE) as meta_capture_dev:
        dev_caps = meta_capture_dev.info.device_capabilities
        assert Capability.VIDEO_CAPTURE not in dev_caps
        assert Capability.STREAMING in dev_caps
        assert Capability.READWRITE in dev_caps
        assert Capability.VIDEO_OUTPUT not in dev_caps
        assert Capability.META_CAPTURE in dev_caps
        assert Capability.META_OUTPUT not in dev_caps

        text = repr(meta_capture_dev.info)
        assert "driver = " in text

        meta_capture_dev.set_input(0)

        assert len(meta_capture_dev.info.frame_sizes) == 0
        assert len(meta_capture_dev.info.formats) > 0

        meta_fmt = meta_capture_dev.get_format(BufferType.META_CAPTURE)
        assert meta_fmt.format in MetaFormat
        assert meta_fmt.width >= 0
        assert meta_fmt.height >= 0


@vivid_only
def test_vivid_inputs():
    with Device(VIVID_CAPTURE_DEVICE) as capture_dev:
        inputs = capture_dev.info.inputs
        assert len(inputs) > 0
        active_input = capture_dev.get_input()
        assert active_input in {inp.index for inp in inputs}
        try:
            capture_dev.set_input(inputs[-1].index)
            assert capture_dev.get_input() == inputs[-1].index
        finally:
            capture_dev.set_input(active_input)


@vivid_only
def test_selection_with_vivid():
    with Device(VIVID_CAPTURE_DEVICE) as capture_dev:
        capture_dev.set_input(1)
        dft_sel = capture_dev.get_selection(BufferType.VIDEO_CAPTURE, SelectionTarget.CROP_DEFAULT)
        assert dft_sel.left >= 0
        assert dft_sel.top >= 0
        assert 0 < dft_sel.width < 10_000
        assert 0 < dft_sel.height < 10_000

        sel = capture_dev.get_selection(BufferType.VIDEO_CAPTURE, SelectionTarget.CROP)
        assert sel.left >= 0
        assert sel.top >= 0
        assert 0 < sel.width < 10_000
        assert 0 < sel.height < 10_000

        capture_dev.set_selection(BufferType.VIDEO_CAPTURE, SelectionTarget.CROP, dft_sel)


def check_frame(frame, width, height, pixel_format, source):
    size = width * height * 3
    assert len(frame.data) == size
    assert frame.nbytes == size
    assert frame.memory == Memory.MMAP
    assert frame.pixel_format == pixel_format
    assert frame.type == BufferType.VIDEO_CAPTURE
    assert frame.width == width
    assert frame.height == height
    assert frame.pixel_format == pixel_format
    if numpy:
        data = frame.array
        assert data.shape == (size,)
        assert data.dtype == numpy.ubyte
    if source in {None, Capability.STREAMING}:
        assert BufferFlag.MAPPED in frame.flags


@vivid_only
@pytest.mark.parametrize("source", [None, Capability.STREAMING])
def test_vivid_capture(source):
    with Device(VIVID_CAPTURE_DEVICE) as capture_dev:
        capture_dev.set_input(0)
        width, height, pixel_format = 640, 480, PixelFormat.RGB24
        capture = VideoCapture(capture_dev, source=source)
        capture.set_format(width, height, pixel_format)
        fmt = capture.get_format()
        assert fmt.width == width
        assert fmt.height == height
        assert fmt.pixel_format == pixel_format

        capture.set_fps(120)
        assert capture.get_fps() >= 60

        with capture:
            stream = iter(capture)
            frame1 = next(stream)
            check_frame(frame1, width, height, pixel_format, source)
            frame2 = next(stream)
            check_frame(frame2, width, height, pixel_format, source)


@vivid_only
@pytest.mark.parametrize("source", [None, Capability.STREAMING])
def test_vivid_gevent_capture(source):
    with Device(VIVID_CAPTURE_DEVICE, io=GeventIO) as capture_dev:
        capture_dev.set_input(0)
        width, height, pixel_format = 640, 480, PixelFormat.RGB24
        capture = VideoCapture(capture_dev, source=source)
        capture.set_format(width, height, pixel_format)
        fmt = capture.get_format()
        assert fmt.width == width
        assert fmt.height == height
        assert fmt.pixel_format == pixel_format

        capture.set_fps(120)
        assert capture.get_fps() >= 60

        with capture:
            stream = iter(capture)
            frame1 = next(stream)
            check_frame(frame1, width, height, pixel_format, source)
            frame2 = next(stream)
            check_frame(frame2, width, height, pixel_format, source)


@vivid_only
@pytest.mark.parametrize("source", [None, Capability.STREAMING])
def test_vivid_sync_capture(source):
    with fopen(VIVID_CAPTURE_DEVICE, rw=True, blocking=True) as fobj:
        capture_dev = Device(fobj)
        capture_dev.set_input(0)
        width, height, pixel_format = 640, 480, PixelFormat.RGB24
        capture = VideoCapture(capture_dev, source=source)
        capture.set_format(width, height, pixel_format)
        fmt = capture.get_format()
        assert fmt.width == width
        assert fmt.height == height
        assert fmt.pixel_format == pixel_format

        capture.set_fps(120)
        assert capture.get_fps() >= 60

        with capture:
            stream = iter(capture)
            frame1 = next(stream)
            check_frame(frame1, width, height, pixel_format, source)
            frame2 = next(stream)
            check_frame(frame2, width, height, pixel_format, source)


@vivid_only
@pytest.mark.asyncio
@pytest.mark.parametrize("source", [None, Capability.STREAMING])
async def test_vivid_async_capture(source):
    with Device(VIVID_CAPTURE_DEVICE) as capture_dev:
        capture_dev.set_input(0)
        width, height, pixel_format = 640, 480, PixelFormat.RGB24
        capture = VideoCapture(capture_dev, source=source)
        capture.set_format(width, height, pixel_format)

        fmt = capture.get_format()
        assert fmt.width == width
        assert fmt.height == height
        assert fmt.pixel_format == pixel_format

        capture.set_fps(120)
        assert capture.get_fps() >= 60
        with capture:
            i = 0
            async for frame in capture:
                check_frame(frame, width, height, pixel_format, source)
                i += 1
                if i > 2:
                    break


@vivid_only
def test_vivid_capture_no_capability():
    with Device(VIVID_OUTPUT_DEVICE) as output_dev:
        stream = iter(output_dev)
        with pytest.raises(V4L2Error):
            next(stream)


@vivid_only
def test_vivid_output():
    with Device(VIVID_OUTPUT_DEVICE) as output_dev:
        output_dev.set_output(0)
        assert output_dev.get_output() == 0

        width, height, pixel_format = 640, 480, PixelFormat.RGB24
        size = width * height * 3
        out = VideoOutput(output_dev)
        out.set_format(width, height, pixel_format)
        fmt = out.get_format()
        assert fmt.width == width
        assert fmt.height == height
        assert fmt.pixel_format == pixel_format
        with out:
            data = os.urandom(size)
            out.write(data)


@vivid_only
def test_vivid_priority():
    with Device(VIVID_CAPTURE_DEVICE) as capture_dev:
        assert isinstance(capture_dev.get_priority(), Priority)

        capture_dev.set_priority(Priority.BACKGROUND)

        assert capture_dev.get_priority() == Priority.BACKGROUND


@vivid_only
def test_vivid_std():
    with Device(VIVID_CAPTURE_DEVICE) as capture_dev:
        capture_dev.set_input(1)
        assert StandardID.PAL_B in capture_dev.get_std()

        assert StandardID.PAL_B in capture_dev.query_std()


@vivid_only
def test_vivid_events():
    with Device(VIVID_CAPTURE_DEVICE) as capture_dev:
        capture_dev.set_input(0)
        brightness = capture_dev.controls.brightness
        capture_dev.subscribe_event(
            EventType.CTRL, brightness.id, EventSubscriptionFlag.ALLOW_FEEDBACK | EventSubscriptionFlag.SEND_INITIAL
        )
        with EventReader(capture_dev) as reader:
            initial_value = brightness.value
            stream = iter(reader)
            event = next(stream)
            assert event.u.ctrl.value == initial_value
            new_value = initial_value + 1 if initial_value < brightness.maximum else initial_value - 1
            brightness.value = new_value
            for event in reader:
                assert event.type == EventType.CTRL
                assert event.u.ctrl.value == new_value
                assert event.u.ctrl.changes == EventControlChange.VALUE
                break


@vivid_only
@pytest.mark.asyncio
async def test_async_vivid_events():
    with Device(VIVID_CAPTURE_DEVICE) as capture_dev:
        capture_dev.set_input(0)
        brightness = capture_dev.controls.brightness
        capture_dev.subscribe_event(EventType.CTRL, brightness.id, EventSubscriptionFlag.ALLOW_FEEDBACK)
        async with EventReader(capture_dev) as reader:
            value = brightness.value
            brightness.value = value + 1 if value < brightness.maximum else value - 1
            async for event in reader:
                assert event.type == EventType.CTRL
                assert event.u.ctrl.changes == EventControlChange.VALUE
                break
