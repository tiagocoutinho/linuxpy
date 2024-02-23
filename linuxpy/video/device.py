#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

"""Human friendly interface to V4L2 (Video 4 Linux 2) subsystem."""

import asyncio
import collections
import contextlib
import copy
import ctypes
import enum
import errno
import fractions
import logging
import mmap
import os
import select
import time
from collections import UserDict
from pathlib import Path

from linuxpy.ctypes import cenum, memcpy
from linuxpy.device import (
    BaseDevice,
    ReentrantOpen,
    iter_device_files,
)
from linuxpy.io import IO
from linuxpy.ioctl import ioctl
from linuxpy.types import AsyncIterator, Buffer, Callable, Iterable, Iterator, Optional, PathLike, Self
from linuxpy.util import add_reader_asyncio, make_find

from . import raw

log = logging.getLogger(__name__)
log_mmap = log.getChild("mmap")


class V4L2Error(Exception):
    """Video for linux 2 error"""


def _enum(name, prefix, klass=enum.IntEnum):
    return klass(
        name,
        ((name.replace(prefix, ""), getattr(raw, name)) for name in dir(raw) if name.startswith(prefix)),
    )


FrameSizeType = raw.Frmsizetypes
FrameIntervalType = raw.Frmivaltypes
Field = raw.Field
ImageFormatFlag = raw.ImageFormatFlag
Capability = raw.Capability
ControlID = raw.ControlID
ControlFlag = raw.ControlFlag
ControlType = raw.CtrlType
ControlClass = raw.ControlClass
SelectionTarget = raw.SelectionTarget
EventType = raw.EventType
IOC = raw.IOC
BufferType = raw.BufType
BufferFlag = raw.BufferFlag
InputType = raw.InputType
PixelFormat = raw.PixelFormat
FrameSizeType = raw.Frmsizetypes
Memory = raw.Memory
InputStatus = raw.InputStatus
InputType = raw.InputType
InputCapabilities = raw.InputCapabilities
Priority = raw.Priority
TimeCodeType = raw.TimeCodeType
TimeCodeFlag = raw.TimeCodeFlag
EventSubscriptionFlag = raw.EventSubscriptionFlag


def V4L2_CTRL_ID2CLASS(id_):
    return id_ & 0x0FFF0000  # unsigned long


def human_pixel_format(ifmt):
    return "".join(map(chr, ((ifmt >> i) & 0xFF for i in range(0, 4 * 8, 8))))


PixelFormat.human_str = lambda self: human_pixel_format(self.value)


Info = collections.namedtuple(
    "Info",
    "driver card bus_info version capabilities device_capabilities "
    "crop_capabilities buffers formats frame_sizes inputs controls",
)

ImageFormat = collections.namedtuple("ImageFormat", "type description flags pixel_format")

Format = collections.namedtuple("Format", "width height pixel_format")

CropCapability = collections.namedtuple("CropCapability", "type bounds defrect pixel_aspect")

Rect = collections.namedtuple("Rect", "left top width height")

Size = collections.namedtuple("Size", "width height")

FrameType = collections.namedtuple("FrameType", "type pixel_format width height min_fps max_fps step_fps")

Input = collections.namedtuple("InputType", "index name type audioset tuner std status capabilities")


INFO_REPR = """\
driver = {info.driver}
card = {info.card}
bus = {info.bus_info}
version = {info.version}
capabilities = {capabilities}
device_capabilities = {device_capabilities}
buffers = {buffers}
"""


def mem_map(fd, length, offset):
    log_mmap.debug("%s, length=%d, offset=%d", fd, length, offset)
    return mmap.mmap(fd, length, offset=offset)


def flag_items(flag):
    return [item for item in type(flag) if item in flag]


def Info_repr(info):
    dcaps = "|".join(cap.name for cap in flag_items(info.device_capabilities))
    caps = "|".join(cap.name for cap in flag_items(info.capabilities))
    buffers = "|".join(buff.name for buff in info.buffers)
    return INFO_REPR.format(info=info, capabilities=caps, device_capabilities=dcaps, buffers=buffers)


Info.__repr__ = Info_repr


def raw_crop_caps_to_crop_caps(stream_type, crop):
    return CropCapability(
        type=stream_type,
        bounds=Rect(
            crop.bounds.left,
            crop.bounds.top,
            crop.bounds.width,
            crop.bounds.height,
        ),
        defrect=Rect(
            crop.defrect.left,
            crop.defrect.top,
            crop.defrect.width,
            crop.defrect.height,
        ),
        pixel_aspect=crop.pixelaspect.numerator / crop.pixelaspect.denominator,
    )


CropCapability.from_raw = raw_crop_caps_to_crop_caps


def iter_read(fd, ioc, indexed_struct, start=0, stop=128, step=1, ignore_einval=False):
    for index in range(start, stop, step):
        indexed_struct.index = index
        try:
            ioctl(fd, ioc, indexed_struct)
            yield indexed_struct
        except OSError as error:
            if error.errno == errno.EINVAL:
                if ignore_einval:
                    continue
                else:
                    break
            elif error.errno == errno.ENOTTY:
                # The ioctl is not supported by the driver
                break
            else:
                raise


def frame_sizes(fd, pixel_formats):
    def get_frame_intervals(fmt, w, h):
        value = raw.v4l2_frmivalenum()
        value.pixel_format = fmt
        value.width = w
        value.height = h
        res = []
        for val in iter_read(fd, IOC.ENUM_FRAMEINTERVALS, value):
            # values come in frame interval (fps = 1/interval)
            try:
                ftype = FrameIntervalType(val.type)
            except ValueError:
                break
            if ftype == FrameIntervalType.DISCRETE:
                min_fps = max_fps = step_fps = fractions.Fraction(val.discrete.denominator / val.discrete.numerator)
            else:
                if val.stepwise.min.numerator == 0:
                    min_fps = 0
                else:
                    min_fps = fractions.Fraction(val.stepwise.min.denominator, val.stepwise.min.numerator)
                if val.stepwise.max.numerator == 0:
                    max_fps = 0
                else:
                    max_fps = fractions.Fraction(val.stepwise.max.denominator, val.stepwise.max.numerator)
                if val.stepwise.step.numerator == 0:
                    step_fps = 0
                else:
                    step_fps = fractions.Fraction(val.stepwise.step.denominator, val.stepwise.step.numerator)
            res.append(
                FrameType(
                    type=ftype,
                    pixel_format=fmt,
                    width=w,
                    height=h,
                    min_fps=min_fps,
                    max_fps=max_fps,
                    step_fps=step_fps,
                )
            )
        if len(res) == 0:
            # If it wasn't possible to get frame interval, report discovered frame size anyway
            res.append(
                FrameType(
                    type=FrameIntervalType.DISCRETE,
                    pixel_format=fmt,
                    width=w,
                    height=h,
                    min_fps=0,
                    max_fps=0,
                    step_fps=0,
                )
            )

        return res

    size = raw.v4l2_frmsizeenum()
    sizes = []
    for pixel_format in pixel_formats:
        size.pixel_format = pixel_format
        size.index = 0
        while True:
            try:
                ioctl(fd, IOC.ENUM_FRAMESIZES, size)
            except OSError:
                break
            if size.type == FrameSizeType.DISCRETE:
                sizes += get_frame_intervals(pixel_format, size.discrete.width, size.discrete.height)
            size.index += 1
    return sizes


def read_capabilities(fd):
    caps = raw.v4l2_capability()
    ioctl(fd, IOC.QUERYCAP, caps)
    return caps


def iter_read_formats(fd, type):
    format = raw.v4l2_fmtdesc()
    format.type = type
    pixel_formats = set(PixelFormat)
    for fmt in iter_read(fd, IOC.ENUM_FMT, format):
        pixel_fmt = fmt.pixelformat
        if pixel_fmt not in pixel_formats:
            log.warning(
                "ignored unknown pixel format %s (%d)",
                human_pixel_format(pixel_fmt),
                pixel_fmt,
            )
            continue
        image_format = ImageFormat(
            type=type,
            flags=ImageFormatFlag(fmt.flags),
            description=fmt.description.decode(),
            pixel_format=PixelFormat(pixel_fmt),
        )
        yield image_format


def iter_read_inputs(fd):
    input = raw.v4l2_input()
    for inp in iter_read(fd, IOC.ENUMINPUT, input):
        input_type = Input(
            index=inp.index,
            name=inp.name.decode(),
            type=InputType(inp.type),
            audioset=inp.audioset,
            tuner=inp.tuner,
            std=inp.std,
            status=InputStatus(inp.status),
            capabilities=InputCapabilities(inp.capabilities),
        )
        yield input_type


def iter_read_controls(fd):
    ctrl = raw.v4l2_query_ext_ctrl()
    nxt = ControlFlag.NEXT_CTRL | ControlFlag.NEXT_COMPOUND
    ctrl.id = nxt
    for ctrl_ext in iter_read(fd, IOC.QUERY_EXT_CTRL, ctrl):
        if ctrl_ext.type != ControlType.CTRL_CLASS:
            yield copy.deepcopy(ctrl_ext)
        ctrl_ext.id |= nxt


def iter_read_menu(fd, ctrl):
    qmenu = raw.v4l2_querymenu()
    qmenu.id = ctrl.id
    for menu in iter_read(
        fd,
        IOC.QUERYMENU,
        qmenu,
        start=ctrl._info.minimum,
        stop=ctrl._info.maximum + 1,
        step=ctrl._info.step,
        ignore_einval=True,
    ):
        yield copy.deepcopy(menu)


def read_info(fd):
    caps = read_capabilities(fd)
    version_tuple = (
        (caps.version & 0xFF0000) >> 16,
        (caps.version & 0x00FF00) >> 8,
        (caps.version & 0x0000FF),
    )
    version_str = ".".join(map(str, version_tuple))
    device_capabilities = Capability(caps.device_caps)
    buffers = [typ for typ in BufferType if Capability[typ.name] in device_capabilities]

    img_fmt_stream_types = {
        BufferType.VIDEO_CAPTURE,
        BufferType.VIDEO_CAPTURE_MPLANE,
        BufferType.VIDEO_OUTPUT,
        BufferType.VIDEO_OUTPUT_MPLANE,
        BufferType.VIDEO_OVERLAY,
    } & set(buffers)

    image_formats = []
    pixel_formats = set()
    for stream_type in img_fmt_stream_types:
        for image_format in iter_read_formats(fd, stream_type):
            image_formats.append(image_format)
            pixel_formats.add(image_format.pixel_format)

    crop = raw.v4l2_cropcap()
    crop_stream_types = {
        BufferType.VIDEO_CAPTURE,
        BufferType.VIDEO_OUTPUT,
        BufferType.VIDEO_OVERLAY,
    } & set(buffers)
    crop_caps = []
    for stream_type in crop_stream_types:
        crop.type = stream_type
        try:
            ioctl(fd, IOC.CROPCAP, crop)
        except OSError:
            continue
        crop_cap = CropCapability.from_raw(stream_type, crop)
        crop_caps.append(crop_cap)

    return Info(
        driver=caps.driver.decode(),
        card=caps.card.decode(),
        bus_info=caps.bus_info.decode(),
        version=version_str,
        capabilities=Capability(caps.capabilities),
        device_capabilities=device_capabilities,
        crop_capabilities=crop_caps,
        buffers=buffers,
        formats=image_formats,
        frame_sizes=frame_sizes(fd, pixel_formats),
        inputs=list(iter_read_inputs(fd)),
        controls=list(iter_read_controls(fd)),
    )


def query_buffer(fd, buffer_type: BufferType, memory: Memory, index: int) -> raw.v4l2_buffer:
    buff = raw.v4l2_buffer()
    buff.type = buffer_type
    buff.memory = memory
    buff.index = index
    buff.reserved = 0
    ioctl(fd, IOC.QUERYBUF, buff)
    return buff


def enqueue_buffer_raw(fd, buff: raw.v4l2_buffer) -> raw.v4l2_buffer:
    if not buff.timestamp.secs:
        buff.timestamp.set_ns()
    ioctl(fd, IOC.QBUF, buff)
    return buff


def enqueue_buffer(fd, buffer_type: BufferType, memory: Memory, size: int, index: int) -> raw.v4l2_buffer:
    buff = raw.v4l2_buffer()
    buff.type = buffer_type
    buff.memory = memory
    buff.bytesused = size
    buff.index = index
    buff.field = Field.NONE
    buff.reserved = 0
    return enqueue_buffer_raw(fd, buff)


def dequeue_buffer(fd, buffer_type: BufferType, memory: Memory) -> raw.v4l2_buffer:
    buff = raw.v4l2_buffer()
    buff.type = buffer_type
    buff.memory = memory
    buff.index = 0
    buff.reserved = 0
    ioctl(fd, IOC.DQBUF, buff)
    return buff


def request_buffers(fd, buffer_type: BufferType, memory: Memory, count: int) -> raw.v4l2_requestbuffers:
    req = raw.v4l2_requestbuffers()
    req.type = buffer_type
    req.memory = memory
    req.count = count
    ioctl(fd, IOC.REQBUFS, req)
    if not req.count:
        raise OSError("Not enough buffer memory")
    return req


def free_buffers(fd, buffer_type: BufferType, memory: Memory) -> raw.v4l2_requestbuffers:
    req = raw.v4l2_requestbuffers()
    req.type = buffer_type
    req.memory = memory
    req.count = 0
    ioctl(fd, IOC.REQBUFS, req)
    return req


def set_raw_format(fd, fmt: raw.v4l2_format):
    ioctl(fd, IOC.S_FMT, fmt)


def set_format(fd, buffer_type: BufferType, width: int, height: int, pixel_format: str = "MJPG"):
    fmt = raw.v4l2_format()
    if isinstance(pixel_format, str):
        pixel_format = raw.v4l2_fourcc(*pixel_format.upper())
    fmt.type = buffer_type
    fmt.fmt.pix.pixelformat = pixel_format
    fmt.fmt.pix.field = Field.ANY
    fmt.fmt.pix.width = width
    fmt.fmt.pix.height = height
    fmt.fmt.pix.bytesperline = 0
    fmt.fmt.pix.sizeimage = 0
    return set_raw_format(fd, fmt)


def get_raw_format(fd, buffer_type):
    fmt = raw.v4l2_format()
    fmt.type = buffer_type
    ioctl(fd, IOC.G_FMT, fmt)
    return fmt


def get_format(fd, buffer_type) -> Format:
    f = get_raw_format(fd, buffer_type)
    return Format(
        width=f.fmt.pix.width,
        height=f.fmt.pix.height,
        pixel_format=PixelFormat(f.fmt.pix.pixelformat),
    )


def get_parm(fd, buffer_type):
    p = raw.v4l2_streamparm()
    p.type = buffer_type
    ioctl(fd, IOC.G_PARM, p)
    return p


def set_fps(fd, buffer_type, fps):
    # v4l2 fraction is u32
    max_denominator = int(min(2**32, 2**32 / fps))
    p = raw.v4l2_streamparm()
    p.type = buffer_type
    fps = fractions.Fraction(fps).limit_denominator(max_denominator)
    if buffer_type == BufferType.VIDEO_CAPTURE:
        p.parm.capture.timeperframe.numerator = fps.denominator
        p.parm.capture.timeperframe.denominator = fps.numerator
    elif buffer_type == BufferType.VIDEO_OUTPUT:
        p.parm.output.timeperframe.numerator = fps.denominator
        p.parm.output.timeperframe.denominator = fps.numerator
    else:
        raise ValueError(f"Unsupported buffer type {buffer_type!r}")
    return ioctl(fd, IOC.S_PARM, p)


def get_fps(fd, buffer_type):
    p = get_parm(fd, buffer_type)
    if buffer_type == BufferType.VIDEO_CAPTURE:
        parm = p.parm.capture
    elif buffer_type == BufferType.VIDEO_OUTPUT:
        parm = p.parm.output
    else:
        raise ValueError(f"Unsupported buffer type {buffer_type!r}")
    return fractions.Fraction(parm.timeperframe.denominator, parm.timeperframe.numerator)


def stream_on(fd, buffer_type):
    btype = cenum(buffer_type)
    return ioctl(fd, IOC.STREAMON, btype)


def stream_off(fd, buffer_type):
    btype = cenum(buffer_type)
    return ioctl(fd, IOC.STREAMOFF, btype)


def set_selection(fd, buffer_type, rectangles):
    sel = raw.v4l2_selection()
    sel.type = buffer_type
    sel.target = SelectionTarget.CROP
    sel.rectangles = len(rectangles)
    rects = (raw.v4l2_ext_rect * sel.rectangles)()

    for i in range(sel.rectangles):
        rects[i].r.left = rectangles[i].left
        rects[i].r.top = rectangles[i].top
        rects[i].r.width = rectangles[i].width
        rects[i].r.height = rectangles[i].height

    sel.pr = ctypes.cast(ctypes.pointer(rects), ctypes.POINTER(raw.v4l2_ext_rect))
    ioctl(fd, IOC.S_SELECTION, sel)


def get_selection(
    fd,
    buffer_type: BufferType,
    target: SelectionTarget = SelectionTarget.CROP_DEFAULT,
    max_nb: int = 128,
):
    sel = raw.v4l2_selection()
    sel.type = buffer_type
    sel.target = target
    sel.rectangles = max_nb
    rects = (raw.v4l2_ext_rect * sel.rectangles)()
    sel.pr = ctypes.cast(ctypes.pointer(rects), ctypes.POINTER(raw.v4l2_ext_rect))
    ioctl(fd, IOC.G_SELECTION, sel)
    if sel.rectangles == 0:
        return Rect(left=sel.r.left, top=sel.r.top, width=sel.r.width, height=sel.r.height)
    return [
        Rect(
            left=rects[i].r.left,
            top=rects[i].r.top,
            width=rects[i].r.width,
            height=rects[i].r.height,
        )
        for i in range(sel.rectangles)
    ]


def get_control(fd, id):
    control = raw.v4l2_control(id)
    ioctl(fd, IOC.G_CTRL, control)
    return control.value


def set_control(fd, id, value):
    control = raw.v4l2_control(id, value)
    ioctl(fd, IOC.S_CTRL, control)


def get_priority(fd) -> Priority:
    priority = ctypes.c_uint()
    ioctl(fd, IOC.G_PRIORITY, priority)
    return Priority(priority.value)


def set_priority(fd, priority: Priority):
    priority = ctypes.c_uint(priority.value)
    ioctl(fd, IOC.S_PRIORITY, priority)


def subscribe_event(
    fd,
    event_type: EventType = EventType.ALL,
    id: int = 0,
    flags: EventSubscriptionFlag = 0,
):
    sub = raw.v4l2_event_subscription()
    sub.type = event_type
    sub.id = id
    sub.flags = flags
    ioctl(fd, IOC.SUBSCRIBE_EVENT, sub)


def unsubscribe_event(fd, event_type: EventType = EventType.ALL, id: int = 0):
    sub = raw.v4l2_event_subscription()
    sub.type = event_type
    sub.id = id
    ioctl(fd, IOC.UNSUBSCRIBE_EVENT, sub)


def deque_event(fd):
    event = raw.v4l2_event()
    ioctl(fd, IOC.DQEVENT, event)
    return event


# Helpers


def create_buffer(fd, buffer_type: BufferType, memory: Memory) -> raw.v4l2_buffer:
    """request + query buffers"""
    buffers = create_buffers(fd, buffer_type, memory, 1)
    return buffers[0]


def create_buffers(fd, buffer_type: BufferType, memory: Memory, count: int) -> list[raw.v4l2_buffer]:
    """request + query buffers"""
    request_buffers(fd, buffer_type, memory, count)
    return [query_buffer(fd, buffer_type, memory, index) for index in range(count)]


def mmap_from_buffer(fd, buff: raw.v4l2_buffer) -> mmap.mmap:
    return mem_map(fd, buff.length, offset=buff.m.offset)


def create_mmap_buffers(fd, buffer_type: BufferType, memory: Memory, count: int) -> list[mmap.mmap]:
    """create buffers + mmap_from_buffer"""
    return [mmap_from_buffer(fd, buff) for buff in create_buffers(fd, buffer_type, memory, count)]


def create_mmap_buffer(fd, buffer_type: BufferType, memory: Memory) -> mmap.mmap:
    return create_mmap_buffers(fd, buffer_type, memory, 1)


def enqueue_buffers(fd, buffer_type: BufferType, memory: Memory, count: int) -> list[raw.v4l2_buffer]:
    return [enqueue_buffer(fd, buffer_type, memory, 0, index) for index in range(count)]


class Device(BaseDevice):
    PREFIX = "/dev/video"

    def __init__(self, name_or_file, read_write=True, io=IO):
        self.info = None
        self.controls = None
        super().__init__(name_or_file, read_write=read_write, io=io)

    def __iter__(self):
        with VideoCapture(self) as stream:
            yield from stream

    async def __aiter__(self):
        with VideoCapture(self) as stream:
            async for frame in stream:
                yield frame

    def _on_open(self):
        self.info = read_info(self.fileno())
        self.controls = Controls.from_device(self)

    def query_buffer(self, buffer_type, memory, index):
        return query_buffer(self.fileno(), buffer_type, memory, index)

    def enqueue_buffer(self, buffer_type: BufferType, memory: Memory, size: int, index: int) -> raw.v4l2_buffer:
        return enqueue_buffer(self.fileno(), buffer_type, memory, size, index)

    def dequeue_buffer(self, buffer_type: BufferType, memory: Memory) -> raw.v4l2_buffer:
        return dequeue_buffer(self.fileno(), buffer_type, memory)

    def request_buffers(self, buffer_type, memory, size):
        return request_buffers(self.fileno(), buffer_type, memory, size)

    def create_buffers(self, buffer_type: BufferType, memory: Memory, count: int) -> list[raw.v4l2_buffer]:
        return create_buffers(self.fileno(), buffer_type, memory, count)

    def free_buffers(self, buffer_type, memory):
        return free_buffers(self.fileno(), buffer_type, memory)

    def enqueue_buffers(self, buffer_type: BufferType, memory: Memory, count: int) -> list[raw.v4l2_buffer]:
        return enqueue_buffers(self.fileno(), buffer_type, memory, count)

    def set_format(
        self,
        buffer_type: BufferType,
        width: int,
        height: int,
        pixel_format: str = "MJPG",
    ):
        return set_format(self.fileno(), buffer_type, width, height, pixel_format=pixel_format)

    def get_format(self, buffer_type) -> Format:
        return get_format(self.fileno(), buffer_type)

    def set_fps(self, buffer_type, fps):
        return set_fps(self.fileno(), buffer_type, fps)

    def get_fps(self, buffer_type):
        return get_fps(self.fileno(), buffer_type)

    def set_selection(self, buffer_type, rectangles):
        return set_selection(self.fileno(), buffer_type, rectangles)

    def get_selection(self, buffer_type, target):
        return get_selection(self.fileno(), buffer_type, target)

    def get_priority(self) -> Priority:
        return get_priority(self.fileno())

    def set_priority(self, priority: Priority):
        set_priority(self.fileno(), priority)

    def stream_on(self, buffer_type):
        self.log.info("Starting %r stream...", buffer_type.name)
        stream_on(self.fileno(), buffer_type)
        self.log.info("%r stream ON", buffer_type.name)

    def stream_off(self, buffer_type):
        self.log.info("Stoping %r stream...", buffer_type.name)
        stream_off(self.fileno(), buffer_type)
        self.log.info("%r stream OFF", buffer_type.name)

    def write(self, data: bytes) -> None:
        self._fobj.write(data)

    def subscribe_event(
        self,
        event_type: EventType = EventType.ALL,
        id: int = 0,
        flags: EventSubscriptionFlag = 0,
    ):
        return subscribe_event(self.fileno(), event_type, id, flags)

    def unsubscribe_event(self, event_type: EventType = EventType.ALL, id: int = 0):
        return unsubscribe_event(self.fileno(), event_type, id)

    def deque_event(self):
        return deque_event(self.fileno())


class Controls(dict):
    @classmethod
    def from_device(cls, device):
        ctrl_type_map = {
            ControlType.BOOLEAN: BooleanControl,
            ControlType.INTEGER: IntegerControl,
            ControlType.INTEGER64: Integer64Control,
            ControlType.MENU: MenuControl,
            ControlType.INTEGER_MENU: MenuControl,
            ControlType.U8: U8Control,
            ControlType.U16: U16Control,
            ControlType.U32: U32Control,
        }
        ctrl_dict = {}

        for ctrl in device.info.controls:
            ctrl_type = ControlType(ctrl.type)
            ctrl_class = ctrl_type_map.get(ctrl_type, GenericControl)
            ctrl_dict[ctrl.id] = ctrl_class(device, ctrl)

        return cls(ctrl_dict)

    def __getattr__(self, key):
        with contextlib.suppress(KeyError):
            return self[key]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{key}'")

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError as error:
            raise AttributeError(key) from error

    def __missing__(self, key):
        for v in self.values():
            if isinstance(v, BaseControl) and (v.config_name == key):
                return v
        raise KeyError(key)

    def used_classes(self):
        return {v.control_class for v in self.values() if isinstance(v, BaseControl)}

    def with_class(self, control_class):
        if isinstance(control_class, ControlClass):
            pass
        elif isinstance(control_class, str):
            cl = [c for c in ControlClass if c.name == control_class.upper()]
            if len(cl) != 1:
                raise ValueError(f"{control_class} is no valid ControlClass")
            control_class = cl[0]
        else:
            raise TypeError(f"control_class expected as ControlClass or str, not {control_class.__class__.__name__}")

        for v in self.values():
            if isinstance(v, BaseControl) and (v.control_class == control_class):
                yield v

    def set_to_default(self):
        for v in self.values():
            if not isinstance(v, BaseControl):
                continue

            with contextlib.suppress(AttributeError):
                v.set_to_default()

    def set_clipping(self, clipping: bool) -> None:
        for v in self.values():
            if isinstance(v, BaseNumericControl):
                v.clipping = clipping


class BaseControl:
    def __init__(self, device, info):
        self.device = device
        self._info = info
        self.id = self._info.id
        self.name = self._info.name.decode()
        self._config_name = None
        self.control_class = ControlClass(V4L2_CTRL_ID2CLASS(self.id))
        self.type = ControlType(self._info.type)

        try:
            self.standard = ControlID(self.id)
        except ValueError:
            self.standard = None

    def __repr__(self):
        repr = str(self.config_name)

        addrepr = self._get_repr()
        addrepr = addrepr.strip()
        if addrepr:
            repr += f" {addrepr}"

        flags = [flag.name.lower() for flag in ControlFlag if ((self._info.flags & flag) == flag)]
        if flags:
            repr += " flags=" + ",".join(flags)

        return f"<{type(self).__name__} {repr}>"

    def _get_repr(self) -> str:
        return ""

    def _get_control(self):
        value = get_control(self.device, self.id)
        return value

    def _set_control(self, value):
        if not self.is_writeable:
            reasons = []
            if self.is_flagged_read_only:
                reasons.append("read-only")
            if self.is_flagged_inactive:
                reasons.append("inactive")
            if self.is_flagged_disabled:
                reasons.append("disabled")
            if self.is_flagged_grabbed:
                reasons.append("grabbed")
            raise AttributeError(f"{self.__class__.__name__} {self.config_name} is not writeable: {', '.join(reasons)}")
        set_control(self.device, self.id, value)

    @property
    def config_name(self) -> str:
        if self._config_name is None:
            res = self.name.lower()
            for r in ("(", ")"):
                res = res.replace(r, "")
            for r in (", ", " "):
                res = res.replace(r, "_")
            self._config_name = res
        return self._config_name

    @property
    def is_flagged_disabled(self) -> bool:
        return (self._info.flags & ControlFlag.DISABLED) == ControlFlag.DISABLED

    @property
    def is_flagged_grabbed(self) -> bool:
        return (self._info.flags & ControlFlag.GRABBED) == ControlFlag.GRABBED

    @property
    def is_flagged_read_only(self) -> bool:
        return (self._info.flags & ControlFlag.READ_ONLY) == ControlFlag.READ_ONLY

    @property
    def is_flagged_update(self) -> bool:
        return (self._info.flags & ControlFlag.UPDATE) == ControlFlag.UPDATE

    @property
    def is_flagged_inactive(self) -> bool:
        return (self._info.flags & ControlFlag.INACTIVE) == ControlFlag.INACTIVE

    @property
    def is_flagged_slider(self) -> bool:
        return (self._info.flags & ControlFlag.SLIDER) == ControlFlag.SLIDER

    @property
    def is_flagged_write_only(self) -> bool:
        return (self._info.flags & ControlFlag.WRITE_ONLY) == ControlFlag.WRITE_ONLY

    @property
    def is_flagged_volatile(self) -> bool:
        return (self._info.flags & ControlFlag.VOLATILE) == ControlFlag.VOLATILE

    @property
    def is_flagged_has_payload(self) -> bool:
        return (self._info.flags & ControlFlag.HAS_PAYLOAD) == ControlFlag.HAS_PAYLOAD

    @property
    def is_flagged_execute_on_write(self) -> bool:
        return (self._info.flags & ControlFlag.EXECUTE_ON_WRITE) == ControlFlag.EXECUTE_ON_WRITE

    @property
    def is_flagged_modify_layout(self) -> bool:
        return (self._info.flags & ControlFlag.MODIFY_LAYOUT) == ControlFlag.MODIFY_LAYOUT

    @property
    def is_flagged_dynamic_array(self) -> bool:
        return (self._info.flags & ControlFlag.DYNAMIC_ARRAY) == ControlFlag.DYNAMIC_ARRAY

    @property
    def is_writeable(self) -> bool:
        return not (
            self.is_flagged_read_only or self.is_flagged_inactive or self.is_flagged_disabled or self.is_flagged_grabbed
        )


class BaseMonoControl(BaseControl):
    def _get_repr(self) -> str:
        repr = f" default={self.default}"
        if not self.is_flagged_write_only:
            repr += f" value={self.value}"
        return repr

    def _convert_read(self, value):
        return value

    @property
    def default(self):
        return self._convert_read(self._info.default_value)

    @property
    def value(self):
        if not self.is_flagged_write_only:
            v = self._get_control()
            return self._convert_read(v)

    def _convert_write(self, value):
        return value

    def _mangle_write(self, value):
        return value

    @value.setter
    def value(self, value):
        v = self._convert_write(value)
        v = self._mangle_write(v)
        self._set_control(v)

    def set_to_default(self):
        self.value = self.default


class GenericControl(BaseMonoControl):
    pass


class BaseNumericControl(BaseMonoControl):
    lower_bound = -(2**31)
    upper_bound = 2**31 - 1

    def __init__(self, device, info, clipping=True):
        super().__init__(device, info)
        self.minimum = self._info.minimum
        self.maximum = self._info.maximum
        self.step = self._info.step
        self.clipping = clipping

        if self.minimum < self.lower_bound:
            raise RuntimeWarning(
                f"Control {self.config_name}'s claimed minimum value {self.minimum} exceeds lower bound of {self.__class__.__name__}"
            )
        if self.maximum > self.upper_bound:
            raise RuntimeWarning(
                f"Control {self.config_name}'s claimed maximum value {self.maximum} exceeds upper bound of {self.__class__.__name__}"
            )

    def _get_repr(self) -> str:
        repr = f" min={self.minimum} max={self.maximum} step={self.step}"
        repr += super()._get_repr()
        return repr

    def _convert_read(self, value):
        return int(value)

    def _convert_write(self, value):
        if isinstance(value, int):
            return value
        else:
            try:
                v = int(value)
            except Exception:
                pass
            else:
                return v
        raise ValueError(f"Failed to coerce {value.__class__.__name__} '{value}' to int")

    def _mangle_write(self, value):
        if self.clipping:
            if value < self.minimum:
                return self.minimum
            elif value > self.maximum:
                return self.maximum
        else:
            if value < self.minimum:
                raise ValueError(f"Control {self.config_name}: {value} exceeds allowed minimum {self.minimum}")
            elif value > self.maximum:
                raise ValueError(f"Control {self.config_name}: {value} exceeds allowed maximum {self.maximum}")
        return value

    def increase(self, steps: int = 1):
        self.value += steps * self.step

    def decrease(self, steps: int = 1):
        self.value -= steps * self.step

    def set_to_minimum(self):
        self.value = self.minimum

    def set_to_maximum(self):
        self.value = self.maximum


class IntegerControl(BaseNumericControl):
    lower_bound = -(2**31)
    upper_bound = 2**31 - 1


class Integer64Control(BaseNumericControl):
    lower_bound = -(2**63)
    upper_bound = 2**63 - 1


class U8Control(BaseNumericControl):
    lower_bound = 0
    upper_bound = 2**8


class U16Control(BaseNumericControl):
    lower_bound = 0
    upper_bound = 2**16


class U32Control(BaseNumericControl):
    lower_bound = 0
    upper_bound = 2**32


class BooleanControl(BaseMonoControl):
    _true = ["true", "1", "yes", "on", "enable"]
    _false = ["false", "0", "no", "off", "disable"]

    def _convert_read(self, value):
        return bool(value)

    def _convert_write(self, value):
        if isinstance(value, bool):
            return value
        elif isinstance(value, str):
            if value in self._true:
                return True
            elif value in self._false:
                return False
        else:
            try:
                v = bool(value)
            except Exception:
                pass
            else:
                return v
        raise ValueError(f"Failed to coerce {value.__class__.__name__} '{value}' to bool")


class MenuControl(BaseMonoControl, UserDict):
    def __init__(self, device, info):
        BaseControl.__init__(self, device, info)
        UserDict.__init__(self)

        if self.type == ControlType.MENU:
            self.data = {item.index: item.name.decode() for item in iter_read_menu(self.device._fobj, self)}
        elif self.type == ControlType.INTEGER_MENU:
            self.data = {item.index: int(item.name) for item in iter_read_menu(self.device._fobj, self)}
        else:
            raise TypeError(f"MenuControl only supports control types MENU or INTEGER_MENU, but not {self.type.name}")

    def _convert_write(self, value):
        return int(value)


class ButtonControl(BaseControl):
    def push(self):
        self._set_control(1)


class BaseCompoundControl(BaseControl):
    def __init__(self, device, info):
        raise NotImplementedError()


class DeviceHelper:
    def __init__(self, device: Device):
        super().__init__()
        self.device = device


class BufferManager(DeviceHelper):
    def __init__(self, device: Device, buffer_type: BufferType, size: int = 2):
        super().__init__(device)
        self.type = buffer_type
        self.size = size
        self.buffers = None
        self.name = type(self).__name__

    def formats(self) -> list:
        formats = self.device.info.formats
        return [fmt for fmt in formats if fmt.type == self.type]

    def crop_capabilities(self):
        crop_capabilities = self.device.info.crop_capabilities
        return [crop for crop in crop_capabilities if crop.type == self.type]

    def query_buffer(self, memory, index):
        return self.device.query_buffer(self.type, memory, index)

    def enqueue_buffer(self, memory: Memory, size: int, index: int) -> raw.v4l2_buffer:
        return self.device.enqueue_buffer(self.type, memory, size, index)

    def dequeue_buffer(self, memory: Memory) -> raw.v4l2_buffer:
        return self.device.dequeue_buffer(self.type, memory)

    def enqueue_buffers(self, memory: Memory) -> list[raw.v4l2_buffer]:
        return self.device.enqueue_buffers(self.type, memory, self.size)

    def free_buffers(self, memory: Memory):
        result = self.device.free_buffers(self.type, memory)
        self.buffers = None
        return result

    def create_buffers(self, memory: Memory):
        if self.buffers:
            raise V4L2Error("buffers already requested. free first")
        self.buffers = self.device.create_buffers(self.type, memory, self.size)
        return self.buffers

    def set_format(self, width, height, pixel_format="MJPG"):
        return self.device.set_format(self.type, width, height, pixel_format)

    def get_format(self) -> Format:
        return self.device.get_format(self.type)

    def set_fps(self, fps):
        return self.device.set_fps(self.type, fps)

    def get_fps(self):
        return self.device.get_fps(self.type)

    def set_selection(self, rectangles):
        return self.device.set_selection(self.type, rectangles)

    def get_selection(self):
        return self.device.get_selection(self.type)

    def stream_on(self):
        self.device.stream_on(self.type)

    def stream_off(self):
        self.device.stream_off(self.type)

    start = stream_on
    stop = stream_off


class Frame:
    """The resulting object from an acquisition."""

    __slots__ = ["format", "buff", "data"]

    def __init__(self, data: bytes, buff: raw.v4l2_buffer, format: Format):
        self.format = format
        self.buff = buff
        self.data = data

    def __bytes__(self):
        return self.data

    def __len__(self):
        return len(self.data)

    def __getitem__(self, index):
        return self.data[index]

    def __repr__(self) -> str:
        return (
            f"<{type(self).__name__} width={self.width}, height={self.height}, "
            f"format={self.pixel_format.name}, frame_nb={self.frame_nb}, timestamp={self.timestamp}>"
        )

    @property
    def width(self):
        return self.format.width

    @property
    def height(self):
        return self.format.height

    @property
    def nbytes(self):
        return self.buff.bytesused

    @property
    def pixel_format(self):
        return PixelFormat(self.format.pixel_format)

    @property
    def index(self):
        return self.buff.index

    @property
    def type(self):
        return BufferType(self.buff.type)

    @property
    def flags(self):
        return BufferFlag(self.buff.flags)

    @property
    def timestamp(self):
        return self.buff.timestamp.secs + self.buff.timestamp.usecs * 1e-6

    @property
    def frame_nb(self):
        return self.buff.sequence

    @property
    def memory(self):
        return Memory(self.buff.memory)

    @property
    def time_type(self):
        if BufferFlag.TIMECODE in self.flags:
            return TimeCodeType(self.buff.timecode.type)

    @property
    def time_flags(self):
        if BufferFlag.TIMECODE in self.flags:
            return TimeCodeFlag(self.buff.timecode.flags)

    @property
    def time_frame(self):
        if BufferFlag.TIMECODE in self.flags:
            return self.buff.timecode.frames

    @property
    def array(self):
        import numpy

        return numpy.frombuffer(bytes(self), dtype="u1")


class VideoCapture(BufferManager):
    def __init__(self, device: Device, size: int = 2, source: Capability = None):
        super().__init__(device, BufferType.VIDEO_CAPTURE, size)
        self.buffer = None
        self.source = source

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *exc):
        self.close()

    def __iter__(self):
        yield from self.buffer

    async def __aiter__(self):
        async for frame in self.buffer:
            yield frame

    def open(self):
        if self.buffer is None:
            self.device.log.info("Preparing for video capture...")
            capabilities = self.device.info.capabilities
            if Capability.VIDEO_CAPTURE not in capabilities:
                raise V4L2Error("device lacks VIDEO_CAPTURE capability")
            source = capabilities if self.source is None else self.source
            if Capability.STREAMING in source:
                self.device.log.info("Video capture using memory map")
                self.buffer = MemoryMap(self)
            elif Capability.READWRITE in source:
                self.device.log.info("Video capture using read")
                self.buffer = Read(self)
            else:
                raise OSError("Device needs to support STREAMING or READWRITE capability")
            self.buffer.open()
            self.stream_on()
            self.device.log.info("Video capture started!")

    def close(self):
        if self.buffer:
            self.device.log.info("Closing video capture...")
            self.stream_off()
            self.buffer.close()
            self.buffer = None
            self.device.log.info("Video capture closed")


class Read(ReentrantOpen):
    def __init__(self, buffer_manager: BufferManager):
        super().__init__()
        self.buffer_manager = buffer_manager
        self.frame_reader = FrameReader(self.device, self.raw_read)
        self.format = None

    def __iter__(self) -> Iterator[Frame]:
        with self.frame_reader:
            while True:
                yield self.frame_reader.read()

    async def __aiter__(self) -> AsyncIterator[Frame]:
        async with self.frame_reader:
            while True:
                yield await self.frame_reader.aread()

    def open(self) -> None:
        self.format = self.buffer_manager.get_format()

    def close(self) -> None:
        self.format = None

    @property
    def device(self) -> Device:
        return self.buffer_manager.device

    def raw_grab(self) -> tuple[bytes, raw.v4l2_buffer]:
        data = os.read(self.device.fileno(), 2**31 - 1)
        ns = time.time_ns()
        buff = raw.v4l2_buffer()
        buff.bytesused = len(data)
        buff.timestamp.set_ns(ns)
        return data, buff

    def raw_read(self) -> Frame:
        data, buff = self.raw_grab()
        return Frame(data, buff, self.format)

    def wait_read(self) -> Frame:
        device = self.device
        if device.io.select is not None:
            device.io.select((device,), (), ())
        return self.raw_read()

    def read(self) -> Frame:
        # first time we check what mode device was opened (blocking vs non-blocking)
        # if file was opened with O_NONBLOCK: DQBUF will not block until a buffer
        # is available for read. So we need to do it here
        if self.device.is_blocking:
            self.read = self.raw_read
        else:
            self.read = self.wait_read
        return self.read()


class MemoryMap(ReentrantOpen):
    def __init__(self, buffer_manager: BufferManager):
        super().__init__()
        self.buffer_manager = buffer_manager
        self.buffers = None
        self.queue = BufferQueue(buffer_manager, Memory.MMAP)
        self.frame_reader = FrameReader(self.device, self.raw_read)
        self.format = None

    def __iter__(self) -> Iterator[Frame]:
        with self.frame_reader:
            while True:
                yield self.frame_reader.read()

    async def __aiter__(self) -> AsyncIterator[Frame]:
        queue = asyncio.Queue(maxsize=10)

        def feed():
            print("start read")
            queue.put_nowait(self.raw_read())
            print("end read")

        with add_reader_asyncio(self.device.fileno(), feed):
            while True:
                print("start wait")
                frame = await queue.get()
                print("end wait")
                yield frame

    @property
    def device(self) -> Device:
        return self.buffer_manager.device

    def open(self) -> None:
        if self.buffers is None:
            self.device.log.info("Reserving buffers...")
            fd = self.device.fileno()
            buffers = self.buffer_manager.create_buffers(Memory.MMAP)
            self.buffers = [mmap_from_buffer(fd, buff) for buff in buffers]
            self.buffer_manager.enqueue_buffers(Memory.MMAP)
            self.format = self.buffer_manager.get_format()
            self.buffer_manager.device.log.info("Buffers reserved")

    def close(self) -> None:
        if self.buffers:
            self.device.log.info("Freeing buffers...")
            for mem in self.buffers:
                mem.close()
            self.buffer_manager.free_buffers(Memory.MMAP)
            self.buffers = None
            self.format = None
            self.device.log.info("Buffers freed")

    def raw_grab(self) -> tuple[Buffer, raw.v4l2_buffer]:
        with self.queue as buff:
            return self.buffers[buff.index][: buff.bytesused], buff

    def raw_read(self) -> Frame:
        data, buff = self.raw_grab()
        return Frame(data, buff, self.format)

    def wait_read(self) -> Frame:
        device = self.device
        if device.io.select is not None:
            device.io.select((device,), (), ())
        return self.raw_read()

    def read(self) -> Frame:
        # first time we check what mode device was opened (blocking vs non-blocking)
        # if file was opened with O_NONBLOCK: DQBUF will not block until a buffer
        # is available for read. So we need to do it here
        if self.device.is_blocking:
            self.read = self.raw_read
        else:
            self.read = self.wait_read
        return self.read()

    def raw_write(self, data: Buffer) -> raw.v4l2_buffer:
        with self.queue as buff:
            size = getattr(data, "nbytes", len(data))
            memory = self.buffers[buff.index]
            memory[:size] = data
            buff.bytesused = size
        return buff

    def wait_write(self, data: Buffer) -> raw.v4l2_buffer:
        device = self.device
        if device.io.select is not None:
            _, r, _ = device.io.select((), (device,), ())
        return self.raw_write(data)

    def write(self, data: Buffer) -> raw.v4l2_buffer:
        # first time we check what mode device was opened (blocking vs non-blocking)
        # if file was opened with O_NONBLOCK: DQBUF will not block until a buffer
        # is available for write. So we need to do it here
        if self.device.is_blocking:
            self.write = self.raw_write
        else:
            self.write = self.wait_write
        return self.write(data)


class EventReader:
    def __init__(self, device: Device, max_queue_size=100):
        self.device = device
        self._loop = None
        self._selector = None
        self._buffer = None
        self._max_queue_size = max_queue_size

    async def __aenter__(self):
        if self.device.is_blocking:
            raise V4L2Error("Cannot use async event reader on blocking device")
        self._buffer = asyncio.Queue(maxsize=self._max_queue_size)
        self._selector = select.epoll()
        self._loop = asyncio.get_event_loop()
        self._loop.add_reader(self._selector.fileno(), self._on_event)
        self._selector.register(self.device.fileno(), select.EPOLLPRI)
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        self._selector.unregister(self.device.fileno())
        self._loop.remove_reader(self._selector.fileno())
        self._selector.close()
        self._selector = None
        self._loop = None
        self._buffer = None

    async def __aiter__(self):
        while True:
            yield await self.aread()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        pass

    def _on_event(self):
        task = self._loop.create_future()
        try:
            self._selector.poll(0)  # avoid blocking
            event = self.device.deque_event()
            task.set_result(event)
        except Exception as error:
            task.set_exception(error)

        buffer = self._buffer
        if buffer.full():
            self.device.log.debug("missed event")
            buffer.popleft()
        buffer.put_nowait(task)

    def read(self, timeout=None):
        if not self.device.is_blocking:
            _, _, exc = self.device.io.select((), (), (self.device,), timeout)
            if not exc:
                return
        return self.device.deque_event()

    async def aread(self):
        """Wait for next event or return last event in queue"""
        task = await self._buffer.get()
        return await task


class FrameReader:
    def __init__(self, device: Device, raw_read: Callable[[], Buffer], max_queue_size: int = 1):
        self.device = device
        self.raw_read = raw_read
        self._loop = None
        self._selector = None
        self._buffer = None
        self._max_queue_size = max_queue_size
        self._device_fd = None

    async def __aenter__(self) -> Self:
        if self.device.is_blocking:
            raise V4L2Error("Cannot use async frame reader on blocking device")
        self._device_fd = self.device.fileno()
        self._buffer = asyncio.Queue(maxsize=self._max_queue_size)
        self._selector = select.epoll()
        self._loop = asyncio.get_event_loop()
        self._loop.add_reader(self._selector.fileno(), self._on_event)
        self._selector.register(self._device_fd, select.POLLIN)
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        with contextlib.suppress(OSError):
            # device may have been closed by now
            self._selector.unregister(self._device_fd)
        self._loop.remove_reader(self._selector.fileno())
        self._selector.close()
        self._selector = None
        self._loop = None
        self._buffer = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_value, tb):
        pass

    def _on_event(self) -> None:
        task = self._loop.create_future()
        try:
            self._selector.poll(0)  # avoid blocking
            data = self.raw_read()
            task.set_result(data)
        except Exception as error:
            task.set_exception(error)

        buffer = self._buffer
        if buffer.full():
            self.device.log.warn("missed frame")
            buffer.get_nowait()
        buffer.put_nowait(task)

    def read(self, timeout: Optional[float] = None) -> Frame:
        if not self.device.is_blocking:
            read, _, _ = self.device.io.select((self.device,), (), (), timeout)
            if not read:
                return
        return self.raw_read()

    async def aread(self) -> Frame:
        """Wait for next frame or return last frame"""
        task = await self._buffer.get()
        return await task


class BufferQueue:
    def __init__(self, buffer_manager: BufferManager, memory: Memory):
        self.buffer_manager = buffer_manager
        self.memory = memory
        self.raw_buffer = None

    def __enter__(self) -> raw.v4l2_buffer:
        # get next buffer that has some data in it
        self.raw_buffer = self.buffer_manager.dequeue_buffer(self.memory)
        return self.raw_buffer

    def __exit__(self, *exc):
        # Make a copy of buffer. We need the original buffer that was sent to
        # dequeue in to keep frame info like frame number, timestamp, etc
        raw_buffer = raw.v4l2_buffer()
        memcpy(raw_buffer, self.raw_buffer)
        enqueue_buffer_raw(self.buffer_manager.device.fileno(), raw_buffer)


class Write(ReentrantOpen):
    def __init__(self, buffer_manager: BufferManager):
        super().__init__()
        self.buffer_manager = buffer_manager

    @property
    def device(self) -> Device:
        return self.buffer_manager.device

    def raw_write(self, data: Buffer) -> None:
        self.device.write(data)

    def wait_write(self, data: Buffer) -> None:
        device = self.device
        if device.io.select is not None:
            _, w, _ = device.io.select((), (device,), ())
        if not w:
            raise OSError("Closed")
        self.raw_write(data)

    def write(self, data: Buffer) -> None:
        # first time we check what mode device was opened (blocking vs non-blocking)
        # if file was opened with O_NONBLOCK: DQBUF will not block until a buffer
        # is available for write. So we need to do it here
        if self.device.is_blocking:
            self.write = self.raw_write
        else:
            self.write = self.wait_write
        return self.write(data)

    def open(self) -> None:
        pass

    def close(self) -> None:
        pass


class VideoOutput(BufferManager):
    def __init__(self, device: Device, size: int = 2, sink: Capability = None):
        super().__init__(device, BufferType.VIDEO_OUTPUT, size)
        self.buffer = None
        self.sink = sink

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def open(self) -> None:
        if self.buffer is not None:
            return
        self.device.log.info("Preparing for video output...")
        capabilities = self.device.info.capabilities
        # Don't check for output capability. Some drivers (ex: v4l2loopback) don't
        # report being output capable so that apps like zoom recognize them
        # if Capability.VIDEO_OUTPUT not in capabilities:
        #    raise V4L2Error("device lacks VIDEO_OUTPUT capability")
        sink = capabilities if self.sink is None else self.sink
        if Capability.STREAMING in sink:
            self.device.log.info("Video output using memory map")
            self.buffer = MemoryMap(self)
        elif Capability.READWRITE in sink:
            self.device.log.info("Video output using write")
            self.buffer = Write(self)
        else:
            raise OSError("Device needs to support STREAMING or READWRITE capability")
        self.buffer.open()
        self.stream_on()
        self.device.log.info("Video output started!")

    def close(self) -> None:
        if self.buffer:
            self.device.log.info("Closing video output...")
            try:
                self.stream_off()
            except Exception as error:
                self.device.log.warning("Failed to close stream: %r", error)
            try:
                self.buffer.close()
            except Exception as error:
                self.device.log.warning("Failed to close buffer: %r", error)
            self.buffer = None
            self.device.log.info("Video output closed")

    def write(self, data: Buffer) -> None:
        self.buffer.write(data)


def iter_video_files(path: PathLike = "/dev") -> Iterable[Path]:
    """Returns an iterator over all video files"""
    return iter_device_files(path=path, pattern="video*")


def iter_devices(path: PathLike = "/dev", **kwargs) -> Iterable[Device]:
    """Returns an iterator over all video devices"""
    return (Device(name, **kwargs) for name in iter_video_files(path=path))


def iter_video_capture_files(path: PathLike = "/dev") -> Iterable[Path]:
    """Returns an iterator over all video files that have CAPTURE capability"""

    def filt(filename):
        with IO.open(filename) as fobj:
            caps = read_capabilities(fobj.fileno())
            return Capability.VIDEO_CAPTURE in Capability(caps.device_caps)

    return filter(filt, iter_video_files(path))


def iter_video_capture_devices(path: PathLike = "/dev", **kwargs) -> Iterable[Device]:
    """Returns an iterator over all video devices that have CAPTURE capability"""
    return (Device(name, **kwargs) for name in iter_video_capture_files(path))


def iter_video_output_files(path: PathLike = "/dev") -> Iterable[Path]:
    """
    Some drivers (ex: v4l2loopback) don't report being output capable so that
    apps like zoom recognize them as valid capture devices so some results might
    be missing
    """

    def filt(filename):
        with IO.open(filename) as fobj:
            caps = read_capabilities(fobj.fileno())
            return Capability.VIDEO_OUTPUT in Capability(caps.device_caps)

    return filter(filt, iter_video_files(path))


def iter_video_output_devices(path: PathLike = "/dev", **kwargs) -> Iterable[Device]:
    """Returns an iterator over all video devices that have VIDEO OUTPUT capability"""
    return (Device(name, **kwargs) for name in iter_video_output_files(path))


find = make_find(iter_devices)
