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

from linuxpy.ctypes import cast, cenum, create_string_buffer, memcpy, string_at
from linuxpy.device import (
    BaseDevice,
    ReentrantOpen,
    iter_device_files,
)
from linuxpy.io import IO
from linuxpy.ioctl import ioctl
from linuxpy.types import AsyncIterator, Buffer, Callable, Iterable, Iterator, Optional, PathLike, Self
from linuxpy.util import astream, bit_indexes, make_find

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
EventControlChange = raw.EventControlChange
IOC = raw.IOC
BufferType = raw.BufType
BufferFlag = raw.BufferFlag
InputType = raw.InputType
PixelFormat = raw.PixelFormat
MetaFormat = raw.MetaFormat
FrameSizeType = raw.Frmsizetypes
Memory = raw.Memory
InputStatus = raw.InputStatus
OutputType = raw.OutputType
InputCapabilities = raw.InputCapabilities
OutputCapabilities = raw.OutputCapabilities
Priority = raw.Priority
TimeCodeType = raw.TimeCodeType
TimeCodeFlag = raw.TimeCodeFlag
EventSubscriptionFlag = raw.EventSubscriptionFlag
StandardID = raw.StandardID


def V4L2_CTRL_ID2CLASS(id_):
    return id_ & 0x0FFF0000  # unsigned long


def human_pixel_format(ifmt):
    return "".join(map(chr, ((ifmt >> i) & 0xFF for i in range(0, 4 * 8, 8))))


PixelFormat.human_str = lambda self: human_pixel_format(self.value)
MetaFormat.human_str = lambda self: human_pixel_format(self.value)


ImageFormat = collections.namedtuple("ImageFormat", "type description flags pixel_format")

MetaFmt = collections.namedtuple("MetaFmt", "format max_buffer_size width height bytes_per_line")

Format = collections.namedtuple("Format", "width height pixel_format size")

CropCapability = collections.namedtuple("CropCapability", "type bounds defrect pixel_aspect")

Rect = collections.namedtuple("Rect", "left top width height")

Size = collections.namedtuple("Size", "width height")

FrameType = collections.namedtuple("FrameType", "type pixel_format width height min_fps max_fps step_fps")

Input = collections.namedtuple("InputType", "index name type audioset tuner std status capabilities")

Output = collections.namedtuple("OutputType", "index name type audioset modulator std capabilities")

Standard = collections.namedtuple("Standard", "index id name frameperiod framelines")


CROP_BUFFER_TYPES = {
    BufferType.VIDEO_CAPTURE,
    BufferType.VIDEO_CAPTURE_MPLANE,
    BufferType.VIDEO_OUTPUT,
    BufferType.VIDEO_OUTPUT_MPLANE,
    BufferType.VIDEO_OVERLAY,
}

IMAGE_FORMAT_BUFFER_TYPES = {
    BufferType.VIDEO_CAPTURE,
    BufferType.VIDEO_CAPTURE_MPLANE,
    BufferType.VIDEO_OUTPUT,
    BufferType.VIDEO_OUTPUT_MPLANE,
    BufferType.VIDEO_OVERLAY,
    BufferType.META_CAPTURE,
    BufferType.META_OUTPUT,
}


def mem_map(fd, length, offset):
    log_mmap.debug("%s, length=%d, offset=%d", fd, length, offset)
    return mmap.mmap(fd, length, offset=offset)


def flag_items(flag):
    return [item for item in type(flag) if item in flag]


def raw_crop_caps_to_crop_caps(crop):
    return CropCapability(
        type=BufferType(crop.type),
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


def raw_read_crop_capabilities(fd, buffer_type: BufferType) -> raw.v4l2_cropcap:
    crop = raw.v4l2_cropcap()
    crop.type = buffer_type
    return ioctl(fd, IOC.CROPCAP, crop)


def read_crop_capabilities(fd, buffer_type: BufferType) -> CropCapability:
    try:
        crop = raw_read_crop_capabilities(fd, buffer_type)
    except OSError as error:
        if error.errno == errno.ENODATA:
            return None
        raise
    return raw_crop_caps_to_crop_caps(crop)


ITER_BREAK = (errno.ENOTTY, errno.ENODATA, errno.EPIPE)


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
            elif error.errno in ITER_BREAK:
                break
            else:
                raise


def iter_read_frame_intervals(fd, fmt, w, h):
    value = raw.v4l2_frmivalenum()
    value.pixel_format = fmt
    value.width = w
    value.height = h
    count = 0
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
        yield FrameType(
            type=ftype,
            pixel_format=fmt,
            width=w,
            height=h,
            min_fps=min_fps,
            max_fps=max_fps,
            step_fps=step_fps,
        )
        count += 1
    if not count:
        # If it wasn't possible to get frame interval, report discovered frame size anyway
        yield FrameType(
            type=FrameIntervalType.DISCRETE,
            pixel_format=fmt,
            width=w,
            height=h,
            min_fps=0,
            max_fps=0,
            step_fps=0,
        )


def iter_read_discrete_frame_sizes(fd, pixel_format):
    size = raw.v4l2_frmsizeenum()
    size.index = 0
    size.pixel_format = pixel_format
    for val in iter_read(fd, IOC.ENUM_FRAMESIZES, size):
        if size.type != FrameSizeType.DISCRETE:
            break
        yield val


def iter_read_pixel_formats_frame_intervals(fd, pixel_formats):
    for pixel_format in pixel_formats:
        for size in iter_read_discrete_frame_sizes(fd, pixel_format):
            yield from iter_read_frame_intervals(fd, pixel_format, size.discrete.width, size.discrete.height)


def read_capabilities(fd):
    caps = raw.v4l2_capability()
    ioctl(fd, IOC.QUERYCAP, caps)
    return caps


def iter_read_formats(fd, type):
    format = raw.v4l2_fmtdesc()
    format.type = type
    pixel_formats = set(PixelFormat)
    meta_formats = set(MetaFormat)
    for fmt in iter_read(fd, IOC.ENUM_FMT, format):
        pixel_fmt = fmt.pixelformat
        if type in {BufferType.VIDEO_CAPTURE, BufferType.VIDEO_OUTPUT}:
            if pixel_fmt not in pixel_formats:
                log.warning(
                    "ignored unknown pixel format %s (%d)",
                    human_pixel_format(pixel_fmt),
                    pixel_fmt,
                )
                continue
            pixel_format = PixelFormat(pixel_fmt)
        elif type in {BufferType.META_CAPTURE, BufferType.META_OUTPUT}:
            if pixel_fmt not in meta_formats:
                log.warning(
                    "ignored unknown meta format %s (%d)",
                    human_pixel_format(pixel_fmt),
                    pixel_fmt,
                )
                continue
            pixel_format = MetaFormat(pixel_fmt)
        image_format = ImageFormat(
            type=type,
            flags=ImageFormatFlag(fmt.flags),
            description=fmt.description.decode(),
            pixel_format=pixel_format,
        )
        yield image_format


def iter_read_inputs(fd):
    input = raw.v4l2_input()
    for inp in iter_read(fd, IOC.ENUMINPUT, input):
        input_type = Input(
            index=inp.index,
            name=inp.name.decode(),
            type=InputType(inp.type),
            audioset=bit_indexes(inp.audioset),
            tuner=inp.tuner,
            std=StandardID(inp.std),
            status=InputStatus(inp.status),
            capabilities=InputCapabilities(inp.capabilities),
        )
        yield input_type


def iter_read_outputs(fd):
    output = raw.v4l2_output()
    for out in iter_read(fd, IOC.ENUMOUTPUT, output):
        output_type = Output(
            index=out.index,
            name=out.name.decode(),
            type=OutputType(out.type),
            audioset=bit_indexes(out.audioset),
            modulator=out.modulator,
            std=StandardID(out.std),
            capabilities=OutputCapabilities(out.capabilities),
        )
        yield output_type


def iter_read_video_standards(fd):
    std = raw.v4l2_standard()
    for item in iter_read(fd, IOC.ENUMSTD, std):
        period = item.frameperiod
        yield Standard(
            index=item.index,
            id=StandardID(item.id),
            name=item.name.decode(),
            frameperiod=fractions.Fraction(period.denominator, period.numerator),
            framelines=item.framelines,
        )


def iter_read_controls(fd):
    ctrl = raw.v4l2_query_ext_ctrl()
    nxt = ControlFlag.NEXT_CTRL | ControlFlag.NEXT_COMPOUND
    ctrl.id = nxt
    for ctrl_ext in iter_read(fd, IOC.QUERY_EXT_CTRL, ctrl):
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


def export_buffer(fd, buffer_type: BufferType, index: int) -> int:
    req = raw.v4l2_exportbuffer(type=buffer_type, index=index)
    return ioctl(fd, IOC.EXPBUF, req).fd


def create_buffers(fd, format: raw.v4l2_format, memory: Memory, count: int) -> raw.v4l2_create_buffers:
    """Create buffers for Memory Mapped or User Pointer or DMA Buffer I/O"""
    req = raw.v4l2_create_buffers()
    req.format = format
    req.memory = memory
    req.count = count
    ioctl(fd, IOC.CREATE_BUFS, req)
    if not req.count:
        raise OSError("Not enough buffer memory")
    return req


def set_raw_format(fd, fmt: raw.v4l2_format):
    return ioctl(fd, IOC.S_FMT, fmt)


def set_format(fd, buffer_type: BufferType, width: int, height: int, pixel_format: str = "MJPG"):
    fmt = raw.v4l2_format()
    if isinstance(pixel_format, str):
        pixel_format = raw.v4l2_fourcc(*pixel_format)
    fmt.type = buffer_type
    fmt.fmt.pix.pixelformat = pixel_format
    fmt.fmt.pix.field = Field.ANY
    fmt.fmt.pix.width = width
    fmt.fmt.pix.height = height
    fmt.fmt.pix.bytesperline = 0
    fmt.fmt.pix.sizeimage = 0
    return set_raw_format(fd, fmt)


def get_raw_format(fd, buffer_type) -> raw.v4l2_format:
    fmt = raw.v4l2_format()
    fmt.type = buffer_type
    ioctl(fd, IOC.G_FMT, fmt)
    return fmt


def get_format(fd, buffer_type) -> Format:
    f = get_raw_format(fd, buffer_type)
    if buffer_type in {BufferType.META_CAPTURE, BufferType.META_OUTPUT}:
        return MetaFmt(
            format=MetaFormat(f.fmt.meta.dataformat),
            max_buffer_size=f.fmt.meta.buffersize,
            width=f.fmt.meta.width,
            height=f.fmt.meta.height,
            bytes_per_line=f.fmt.meta.bytesperline,
        )
    return Format(
        width=f.fmt.pix.width,
        height=f.fmt.pix.height,
        pixel_format=PixelFormat(f.fmt.pix.pixelformat),
        size=f.fmt.pix.sizeimage,
    )


def try_raw_format(fd, fmt: raw.v4l2_format):
    ioctl(fd, IOC.TRY_FMT, fmt)


def try_format(fd, buffer_type: BufferType, width: int, height: int, pixel_format: str = "MJPG"):
    fmt = raw.v4l2_format()
    if isinstance(pixel_format, str):
        pixel_format = raw.v4l2_fourcc(*pixel_format)
    fmt.type = buffer_type
    fmt.fmt.pix.pixelformat = pixel_format
    fmt.fmt.pix.field = Field.ANY
    fmt.fmt.pix.width = width
    fmt.fmt.pix.height = height
    fmt.fmt.pix.bytesperline = 0
    fmt.fmt.pix.sizeimage = 0
    return try_raw_format(fd, fmt)


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


def set_selection(fd, buffer_type, target, rectangle):
    sel = raw.v4l2_selection()
    sel.type = buffer_type
    sel.target = target
    sel.r.left = rectangle.left
    sel.r.top = rectangle.top
    sel.r.width = rectangle.width
    sel.r.height = rectangle.height
    ioctl(fd, IOC.S_SELECTION, sel)


def get_selection(
    fd,
    buffer_type: BufferType,
    target: SelectionTarget = SelectionTarget.CROP,
) -> Rect:
    sel = raw.v4l2_selection()
    sel.type = buffer_type
    sel.target = target
    ioctl(fd, IOC.G_SELECTION, sel)
    return Rect(left=sel.r.left, top=sel.r.top, width=sel.r.width, height=sel.r.height)


def get_control(fd, id):
    control = raw.v4l2_control(id)
    ioctl(fd, IOC.G_CTRL, control)
    return control.value


CTRL_TYPE_CTYPE_ARRAY = {
    ControlType.U8: ctypes.c_uint8,
    ControlType.U16: ctypes.c_uint16,
    ControlType.U32: ctypes.c_uint32,
    ControlType.INTEGER: ctypes.c_int,
    ControlType.INTEGER64: ctypes.c_int64,
}


CTRL_TYPE_CTYPE_STRUCT = {
    # ControlType.AREA: raw.v4l2_area,
}


def _struct_for_ctrl_type(ctrl_type):
    ctrl_type = ControlType(ctrl_type).name.lower()
    name = f"v4l2_ctrl_{ctrl_type}"
    try:
        return getattr(raw, name)
    except AttributeError:
        name = f"v4l2_{ctrl_type}"
        return getattr(raw, name)


def get_ctrl_type_struct(ctrl_type):
    struct = CTRL_TYPE_CTYPE_STRUCT.get(ctrl_type)
    if struct is None:
        struct = _struct_for_ctrl_type(ctrl_type)
        CTRL_TYPE_CTYPE_STRUCT[ctrl_type] = struct
    return struct


def convert_to_ctypes_array(lst, depth, ctype):
    """Convert a list (arbitrary depth) to a ctypes array."""
    if depth == 1:
        return (ctype * len(lst))(*lst)

    # Recursive case: we need to process the sub-lists first
    sub_arrays = [convert_to_ctypes_array(sub_lst, depth - 1, ctype) for sub_lst in lst]
    array_type = len(sub_arrays) * type(sub_arrays[0])  # Create the array type
    return array_type(*sub_arrays)


def _prepare_read_control_value(control: raw.v4l2_query_ext_ctrl, raw_control: raw.v4l2_ext_control):
    raw_control.id = control.id
    has_payload = ControlFlag.HAS_PAYLOAD in ControlFlag(control.flags)
    if has_payload:
        if control.type == ControlType.STRING:
            size = control.maximum + 1
            payload = ctypes.create_string_buffer(size)
            raw_control.string = payload
            raw_control.size = size
        else:
            ctype = CTRL_TYPE_CTYPE_ARRAY.get(control.type)
            raw_control.size = control.elem_size * control.elems
            if ctype is None:
                ctype = get_ctrl_type_struct(control.type)
                payload = ctype()
                raw_control.ptr = ctypes.cast(ctypes.pointer(payload), ctypes.c_void_p)
            else:
                for i in range(control.nr_of_dims):
                    ctype *= control.dims[i]
                payload = ctype()
                raw_control.size = control.elem_size * control.elems
                raw_control.ptr = ctypes.cast(payload, ctypes.c_void_p)
        return payload


def _get_control_value(control: raw.v4l2_query_ext_ctrl, raw_control: raw.v4l2_ext_control, data):
    if data is None:
        if control.type == ControlType.INTEGER64:
            return raw_control.value64
        return raw_control.value
    else:
        if control.type == ControlType.STRING:
            return data.value.decode()
        return data


def get_controls_values(fd, controls: list[raw.v4l2_query_ext_ctrl], which=raw.ControlWhichValue.CUR_VAL, request_fd=0):
    n = len(controls)
    ctrls = raw.v4l2_ext_controls()
    ctrls.which = which
    ctrls.count = n
    ctrls.request_fd = request_fd
    ctrls.controls = (n * raw.v4l2_ext_control)()
    values = [_prepare_read_control_value(*args) for args in zip(controls, ctrls.controls)]
    ioctl(fd, IOC.G_EXT_CTRLS, ctrls)
    return [_get_control_value(*args) for args in zip(controls, ctrls.controls, values)]


def set_control(fd, id, value):
    control = raw.v4l2_control(id, value)
    ioctl(fd, IOC.S_CTRL, control)


def _prepare_write_controls_values(control: raw.v4l2_query_ext_ctrl, value: object, raw_control: raw.v4l2_ext_control):
    raw_control.id = control.id
    has_payload = ControlFlag.HAS_PAYLOAD in ControlFlag(control.flags)
    if has_payload:
        if control.type == ControlType.STRING:
            raw_control.string = ctypes.create_string_buffer(value.encode())
            raw_control.size = len(value) + 1
        else:
            array_type = CTRL_TYPE_CTYPE_ARRAY.get(control.type)
            raw_control.size = control.elem_size * control.elems
            # a struct: assume value is proper raw struct
            if array_type is None:
                value = ctypes.pointer(value)
            else:
                value = convert_to_ctypes_array(value, control.nr_of_dims, array_type)
            ptr = ctypes.cast(value, ctypes.c_void_p)
            raw_control.ptr = ptr
    else:
        if control.type == ControlType.INTEGER64:
            raw_control.value64 = value
        else:
            raw_control.value = value


def set_controls_values(
    fd, controls_values: list[tuple[raw.v4l2_query_ext_ctrl, object]], which=raw.ControlWhichValue.CUR_VAL, request_fd=0
):
    n = len(controls_values)
    ctrls = raw.v4l2_ext_controls()
    ctrls.which = which
    ctrls.count = n
    ctrls.request_fd = request_fd
    ctrls.controls = (n * raw.v4l2_ext_control)()
    for (control, value), raw_control in zip(controls_values, ctrls.controls):
        _prepare_write_controls_values(control, value, raw_control)
    ioctl(fd, IOC.S_EXT_CTRLS, ctrls)


def get_priority(fd) -> Priority:
    priority = ctypes.c_uint()
    ioctl(fd, IOC.G_PRIORITY, priority)
    return Priority(priority.value)


def set_priority(fd, priority: Priority):
    priority = ctypes.c_uint(priority.value)
    ioctl(fd, IOC.S_PRIORITY, priority)


def subscribe_event(
    fd,
    event_type: EventType,
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


def deque_event(fd) -> raw.v4l2_event:
    event = raw.v4l2_event()
    return ioctl(fd, IOC.DQEVENT, event)


def set_edid(fd, edid):
    if len(edid) % 128:
        raise ValueError(f"EDID length {len(edid)} is not multiple of 128")
    edid_struct = raw.v4l2_edid()
    edid_struct.pad = 0
    edid_struct.start_block = 0
    edid_struct.blocks = len(edid) // 128
    edid_array = create_string_buffer(edid)
    edid_struct.edid = cast(edid_array, type(edid_struct.edid))
    ioctl(fd, IOC.S_EDID, edid_struct)


def clear_edid(fd):
    set_edid(fd, b"")


def get_edid(fd):
    edid_struct = raw.v4l2_edid()
    ioctl(fd, IOC.G_EDID, edid_struct)
    if edid_struct.blocks == 0:
        return b""
    edid_len = 128 * edid_struct.blocks
    edid_array = create_string_buffer(b"\0" * edid_len)
    edid_struct.edid = cast(edid_array, type(edid_struct.edid))
    ioctl(fd, IOC.G_EDID, edid_struct)
    return string_at(edid_struct.edid, edid_len)


def get_input(fd):
    inp = ctypes.c_uint()
    ioctl(fd, IOC.G_INPUT, inp)
    return inp.value


def set_input(fd, index: int):
    index = ctypes.c_uint(index)
    ioctl(fd, IOC.S_INPUT, index)


def get_output(fd):
    out = ctypes.c_uint()
    ioctl(fd, IOC.G_OUTPUT, out)
    return out.value


def set_output(fd, index: int):
    index = ctypes.c_uint(index)
    ioctl(fd, IOC.S_OUTPUT, index)


def get_std(fd) -> StandardID:
    out = ctypes.c_uint64()
    ioctl(fd, IOC.G_STD, out)
    return StandardID(out.value)


def set_std(fd, std):
    ioctl(fd, IOC.S_STD, std)


def query_std(fd) -> StandardID:
    out = ctypes.c_uint64()
    ioctl(fd, IOC.QUERYSTD, out)
    return StandardID(out.value)


SubdevFormat = collections.namedtuple(
    "SubdevFormat", "pad which width height code field colorspace quantization xfer_func flags stream"
)


def _translate_subdev_format(fmt: raw.v4l2_subdev_format):
    return SubdevFormat(
        pad=fmt.pad,
        which=raw.SubdevFormatWhence(fmt.which),
        width=fmt.format.width,
        height=fmt.format.height,
        code=raw.MbusPixelcode(fmt.format.code),
        field=raw.Field(fmt.format.field),
        colorspace=raw.Colorspace(fmt.format.colorspace),
        quantization=raw.Quantization(fmt.format.quantization),
        xfer_func=raw.XferFunc(fmt.format.xfer_func),
        flags=raw.MbusFrameFormatFlag(fmt.format.flags),
        stream=fmt.stream,
    )


def get_subdevice_format(fd, pad: int = 0) -> raw.v4l2_subdev_format:
    fmt = raw.v4l2_subdev_format(pad=pad, which=raw.SubdevFormatWhence.ACTIVE)
    return _translate_subdev_format(ioctl(fd, IOC.SUBDEV_G_FMT, fmt))


# Helpers


def request_and_query_buffer(fd, buffer_type: BufferType, memory: Memory) -> raw.v4l2_buffer:
    """request + query buffers"""
    buffers = request_and_query_buffers(fd, buffer_type, memory, 1)
    return buffers[0]


def request_and_query_buffers(fd, buffer_type: BufferType, memory: Memory, count: int) -> list[raw.v4l2_buffer]:
    """request + query buffers"""
    request_buffers(fd, buffer_type, memory, count)
    return [query_buffer(fd, buffer_type, memory, index) for index in range(count)]


def mmap_from_buffer(fd, buff: raw.v4l2_buffer) -> mmap.mmap:
    return mem_map(fd, buff.length, offset=buff.m.offset)


def create_mmap_buffers(fd, buffer_type: BufferType, memory: Memory, count: int) -> list[mmap.mmap]:
    """create buffers + mmap_from_buffer"""
    return [mmap_from_buffer(fd, buff) for buff in request_and_query_buffers(fd, buffer_type, memory, count)]


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
        self.info = InfoEx(self)
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
        return request_and_query_buffers(self.fileno(), buffer_type, memory, count)

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

    def set_selection(self, buffer_type, target, rectangle):
        return set_selection(self.fileno(), buffer_type, target, rectangle)

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

    def set_edid(self, edid):
        set_edid(self.fileno(), edid)

    def clear_edid(self):
        clear_edid(self.fileno())

    def get_edid(self):
        return get_edid(self.fileno())

    def get_input(self):
        return get_input(self.fileno())

    def set_input(self, index: int):
        return set_input(self.fileno(), index)

    def get_output(self):
        return get_output(self.fileno())

    def set_output(self, index: int):
        return set_output(self.fileno(), index)

    def get_std(self) -> StandardID:
        return get_std(self.fileno())

    def set_std(self, std):
        return set_std(self.fileno(), std)

    def query_std(self) -> StandardID:
        return query_std(self.fileno())


class SubDevice(BaseDevice):
    def get_format(self, pad: int = 0) -> SubdevFormat:
        return get_subdevice_format(self, pad=pad)


def create_artificial_control_class(class_id):
    return raw.v4l2_query_ext_ctrl(
        id=class_id | 1,
        name=b"Generic Controls",
        type=ControlType.CTRL_CLASS,
    )


class Controls(dict):
    def __init__(self, device: Device):
        super().__init__()
        self.__dict__["_device"] = device
        self.__dict__["_initialized"] = False

    def _init_if_needed(self):
        if not self._initialized:
            self._load()
            self.__dict__["_initialized"] = True

    def __getitem__(self, name):
        self._init_if_needed()
        return super().__getitem__(name)

    def __len__(self):
        self._init_if_needed()
        return super().__len__()

    def _load(self):
        ctrl_type_map = {
            ControlType.BOOLEAN: BooleanControl,
            ControlType.INTEGER: IntegerControl,
            ControlType.INTEGER64: Integer64Control,
            ControlType.MENU: MenuControl,
            ControlType.INTEGER_MENU: MenuControl,
            ControlType.U8: U8Control,
            ControlType.U16: U16Control,
            ControlType.U32: U32Control,
            ControlType.BUTTON: ButtonControl,
        }
        classes = {}
        for ctrl in self._device.info.controls:
            ctrl_type = ControlType(ctrl.type)
            ctrl_class_id = V4L2_CTRL_ID2CLASS(ctrl.id)
            if ctrl_type == ControlType.CTRL_CLASS:
                classes[ctrl_class_id] = ctrl
            else:
                klass = classes.get(ctrl_class_id)
                if klass is None:
                    klass = create_artificial_control_class(ctrl_class_id)
                    classes[ctrl_class_id] = klass
                has_payload = ControlFlag.HAS_PAYLOAD in ControlFlag(ctrl.flags)
                if has_payload:
                    ctrl_class = CompoundControl
                else:
                    ctrl_class = ctrl_type_map.get(ctrl_type, GenericControl)
                self[ctrl.id] = ctrl_class(self._device, ctrl, klass)

    @classmethod
    def from_device(cls, device):
        """Deprecated: backward compatible. Please use Controls(device) constructor directly"""
        return cls(device)

    def __getattr__(self, key):
        with contextlib.suppress(KeyError):
            return self[key]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{key}'")

    def __setattr__(self, key, value):
        self._init_if_needed()
        self[key] = value

    def __missing__(self, key):
        self._init_if_needed()
        for v in self.values():
            if isinstance(v, BaseControl) and (v.config_name == key):
                return v
        raise KeyError(key)

    def values(self):
        self._init_if_needed()
        return super().values()

    def used_classes(self):
        class_map = {v.control_class.id: v.control_class for v in self.values() if isinstance(v, BaseControl)}
        return list(class_map.values())

    def with_class(self, control_class):
        if isinstance(control_class, str):
            control_class = ControlClass[control_class.upper()]
        elif isinstance(control_class, int):
            control_class = ControlClass(control_class)
        elif not isinstance(control_class, ControlClass):
            control_class = ControlClass(control_class.id - 1)
        for v in self.values():
            if not isinstance(v, BaseControl):
                continue
            if v.control_class.id - 1 == control_class:
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
    def __init__(self, device, info, control_class):
        self.device = device
        self._info = info
        self.id = self._info.id
        self.name = self._info.name.decode()
        self._config_name = None
        self.control_class = control_class
        self.type = ControlType(self._info.type)
        self.flags = ControlFlag(self._info.flags)

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

        if self.flags:
            flags = [flag.name.lower() for flag in ControlFlag if ((self._info.flags & flag) == flag)]
            repr += " flags=" + ",".join(flags)

        return f"<{type(self).__name__} {repr}>"

    def _get_repr(self) -> str:
        return ""

    def _get_control(self):
        # value = get_controls_values(self.device, [self._info])[0]
        value = get_controls_values(self.device, (self._info,))[0]
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
        set_controls_values(self.device, ((self._info, value),))

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
        return ControlFlag.DISABLED in self.flags

    @property
    def is_flagged_grabbed(self) -> bool:
        return ControlFlag.GRABBED in self.flags

    @property
    def is_flagged_read_only(self) -> bool:
        return ControlFlag.READ_ONLY in self.flags

    @property
    def is_flagged_update(self) -> bool:
        return ControlFlag.UPDATE in self.flags

    @property
    def is_flagged_inactive(self) -> bool:
        return ControlFlag.INACTIVE in self.flags

    @property
    def is_flagged_slider(self) -> bool:
        return ControlFlag.SLIDER in self.flags

    @property
    def is_flagged_write_only(self) -> bool:
        return ControlFlag.WRITE_ONLY in self.flags

    @property
    def is_flagged_volatile(self) -> bool:
        return ControlFlag.VOLATILE in self.flags

    @property
    def is_flagged_has_payload(self) -> bool:
        return ControlFlag.HAS_PAYLOAD in self.flags

    @property
    def is_flagged_execute_on_write(self) -> bool:
        return ControlFlag.EXECUTE_ON_WRITE in self.flags

    @property
    def is_flagged_modify_layout(self) -> bool:
        return ControlFlag.MODIFY_LAYOUT in self.flags

    @property
    def is_flagged_dynamic_array(self) -> bool:
        return ControlFlag.DYNAMIC_ARRAY in self.flags

    @property
    def is_writeable(self) -> bool:
        return not (self.is_flagged_read_only or self.is_flagged_disabled or self.is_flagged_grabbed)


class BaseMonoControl(BaseControl):
    def _get_repr(self) -> str:
        repr = f" default={self.default}"
        if not self.is_flagged_write_only:
            try:
                repr += f" value={self.value}"
            except Exception as error:
                repr += f" value=<error: {error!r}>"
        return repr

    def _convert_read(self, value):
        return value

    @property
    def default(self):
        default = get_controls_values(self.device, (self._info,), raw.ControlWhichValue.DEF_VAL)[0]
        return self._convert_read(default)

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

    def __init__(self, device, info, control_class, clipping=True):
        super().__init__(device, info, control_class)
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
        return value

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
    def __init__(self, device, info, control_class):
        BaseControl.__init__(self, device, info, control_class)
        UserDict.__init__(self)

        if self.type == ControlType.MENU:
            self.data = {item.index: item.name.decode() for item in iter_read_menu(self.device, self)}
        elif self.type == ControlType.INTEGER_MENU:
            self.data = {item.index: item.value for item in iter_read_menu(self.device, self)}
        else:
            raise TypeError(f"MenuControl only supports control types MENU or INTEGER_MENU, but not {self.type.name}")

    def _convert_write(self, value):
        return int(value)


class ButtonControl(BaseControl):
    def push(self):
        self._set_control(1)


class CompoundControl(BaseControl):
    @property
    def default(self):
        return get_controls_values(self.device, [self._info], raw.ControlWhichValue.DEF_VAL)[0]

    @property
    def value(self):
        if not self.is_flagged_write_only:
            return get_controls_values(self.device, [self._info])[0]

    @value.setter
    def value(self, value):
        set_controls_values(self.device, ((self._info, value),))


class DeviceHelper:
    def __init__(self, device: Device):
        super().__init__()
        self.device = device


class InfoEx(DeviceHelper):
    INFO_REPR = """\
driver = {info.driver}
card = {info.card}
bus = {info.bus_info}
version = {info.version}
capabilities = {capabilities}
device_capabilities = {device_capabilities}
buffers = {buffers}
"""

    def __init__(self, device: "Device"):
        self.device = device
        self._raw_capabilities_cache = None

    def __repr__(self):
        dcaps = "|".join(cap.name for cap in flag_items(self.device_capabilities))
        caps = "|".join(cap.name for cap in flag_items(self.capabilities))
        buffers = "|".join(buff.name for buff in self.buffers)
        return self.INFO_REPR.format(info=self, capabilities=caps, device_capabilities=dcaps, buffers=buffers)

    @property
    def raw_capabilities(self) -> raw.v4l2_capability:
        if self._raw_capabilities_cache is None:
            self._raw_capabilities_cache = read_capabilities(self.device)
        return self._raw_capabilities_cache

    @property
    def driver(self) -> str:
        return self.raw_capabilities.driver.decode()

    @property
    def card(self) -> str:
        return self.raw_capabilities.card.decode()

    @property
    def bus_info(self) -> str:
        return self.raw_capabilities.bus_info.decode()

    @property
    def version_tuple(self) -> tuple:
        caps = self.raw_capabilities
        return (
            (caps.version & 0xFF0000) >> 16,
            (caps.version & 0x00FF00) >> 8,
            (caps.version & 0x0000FF),
        )

    @property
    def version(self) -> str:
        return ".".join(map(str, self.version_tuple))

    @property
    def capabilities(self) -> Capability:
        return Capability(self.raw_capabilities.capabilities)

    @property
    def device_capabilities(self) -> Capability:
        return Capability(self.raw_capabilities.device_caps)

    @property
    def buffers(self):
        dev_caps = self.device_capabilities
        return [typ for typ in BufferType if Capability[typ.name] in dev_caps]

    def get_crop_capabilities(self, buffer_type: BufferType) -> CropCapability:
        return read_crop_capabilities(self.device, buffer_type)

    @property
    def crop_capabilities(self) -> dict[BufferType, CropCapability]:
        buffer_types = CROP_BUFFER_TYPES & set(self.buffers)
        result = {}
        for buffer_type in buffer_types:
            crop_cap = self.get_crop_capabilities(buffer_type)
            if crop_cap is None:
                continue
            result[buffer_type] = crop_cap
        return result

    @property
    def formats(self):
        img_fmt_buffer_types = IMAGE_FORMAT_BUFFER_TYPES & set(self.buffers)
        return [
            image_format
            for buffer_type in img_fmt_buffer_types
            for image_format in iter_read_formats(self.device, buffer_type)
        ]

    @property
    def frame_sizes(self):
        pixel_formats = {fmt.pixel_format for fmt in self.formats}
        return list(iter_read_pixel_formats_frame_intervals(self.device, pixel_formats))

    @property
    def inputs(self) -> list[Input]:
        return list(iter_read_inputs(self.device))

    @property
    def outputs(self):
        return list(iter_read_outputs(self.device))

    @property
    def controls(self):
        return list(iter_read_controls(self.device))

    @property
    def video_standards(self) -> list[Standard]:
        """List of video standards for the active input"""
        return list(iter_read_video_standards(self.device))


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

    def request_buffers(self, memory: Memory):
        if self.buffers:
            raise V4L2Error("buffers already requested. free first")
        self.buffers = self.device.request_buffers(self.type, memory, self.size)
        return self.buffers

    def set_format(self, width, height, pixel_format="MJPG"):
        return self.device.set_format(self.type, width, height, pixel_format)

    def get_format(self) -> Format:
        return self.device.get_format(self.type)

    def set_fps(self, fps):
        return self.device.set_fps(self.type, fps)

    def get_fps(self):
        return self.device.get_fps(self.type)

    def set_selection(self, target, rectangle):
        return self.device.set_selection(self.type, target, rectangle)

    def get_selection(self, target):
        return self.device.get_selection(self.type, target)

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

        return numpy.frombuffer(self.data, dtype="u1")


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
            capabilities = self.device.info.device_capabilities
            if Capability.VIDEO_CAPTURE not in capabilities:
                raise V4L2Error("device lacks VIDEO_CAPTURE capability")
            source = capabilities if self.source is None else self.source
            if Capability.STREAMING in source:
                self.device.log.info("Video capture using memory map")
                self.buffer = MemoryMap(self)
                # self.buffer = UserPtr(self)
            elif Capability.READWRITE in source:
                self.device.log.info("Video capture using read")
                self.buffer = ReadSource(self)
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


class ReadSource(ReentrantOpen):
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


class MemorySource(ReentrantOpen):
    def __init__(self, buffer_manager: BufferManager, source: Memory):
        super().__init__()
        self.buffer_manager = buffer_manager
        self.source = source
        self.buffers = None
        self.queue = BufferQueue(buffer_manager, source)
        self.frame_reader = FrameReader(self.device, self.raw_read)
        self.format = None

    def __iter__(self) -> Iterator[Frame]:
        with self.frame_reader:
            yield from self.frame_reader

    def __aiter__(self) -> AsyncIterator[Frame]:
        return astream(self.device.fileno(), self.raw_read)

    @property
    def device(self) -> Device:
        return self.buffer_manager.device

    def prepare_buffers(self):
        raise NotImplementedError

    def release_buffers(self):
        self.device.log.info("Freeing buffers...")
        self.buffer_manager.free_buffers(self.source)
        self.buffers = None
        self.format = None
        self.device.log.info("Buffers freed")

    def open(self) -> None:
        self.format = self.buffer_manager.get_format()
        if self.buffers is None:
            self.prepare_buffers()

    def close(self) -> None:
        if self.buffers:
            self.release_buffers()

    def grab_from_buffer(self, buff: raw.v4l2_buffer):
        # return memoryview(self.buffers[buff.index])[: buff.bytesused], buff
        return self.buffers[buff.index][: buff.bytesused], buff

    def raw_grab(self) -> tuple[Buffer, raw.v4l2_buffer]:
        with self.queue as buff:
            return self.grab_from_buffer(buff)

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


class UserPtr(MemorySource):
    def __init__(self, buffer_manager: BufferManager):
        super().__init__(buffer_manager, Memory.USERPTR)

    def prepare_buffers(self):
        self.device.log.info("Reserving buffers...")
        self.buffer_manager.create_buffers(self.source)
        size = self.format.size
        self.buffers = []
        for index in range(self.buffer_manager.size):
            data = ctypes.create_string_buffer(size)
            self.buffers.append(data)
            buff = raw.v4l2_buffer()
            buff.index = index
            buff.type = self.buffer_manager.type
            buff.memory = self.source
            buff.m.userptr = ctypes.addressof(data)
            buff.length = size
            self.queue.enqueue(buff)
        self.device.log.info("Buffers reserved")


class MemoryMap(MemorySource):
    def __init__(self, buffer_manager: BufferManager):
        super().__init__(buffer_manager, Memory.MMAP)

    def prepare_buffers(self):
        self.device.log.info("Reserving buffers...")
        buffers = self.buffer_manager.create_buffers(self.source)
        fd = self.device.fileno()
        self.buffers = [mmap_from_buffer(fd, buff) for buff in buffers]
        self.buffer_manager.enqueue_buffers(Memory.MMAP)
        self.format = self.buffer_manager.get_format()
        self.device.log.info("Buffers reserved")


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

    def __iter__(self):
        while True:
            yield self.read()

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

    def __iter__(self):
        while True:
            yield self.read()

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

    def enqueue(self, buff: raw.v4l2_buffer):
        enqueue_buffer_raw(self.buffer_manager.device.fileno(), buff)

    def dequeue(self):
        return self.buffer_manager.dequeue_buffer(self.memory)

    def __enter__(self) -> raw.v4l2_buffer:
        # get next buffer that has some data in it
        self.raw_buffer = self.dequeue()
        return self.raw_buffer

    def __exit__(self, *exc):
        # Make a copy of buffer. We need the original buffer that was sent to
        # dequeue in to keep frame info like frame number, timestamp, etc
        raw_buffer = raw.v4l2_buffer()
        memcpy(raw_buffer, self.raw_buffer)
        self.enqueue(raw_buffer)


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
