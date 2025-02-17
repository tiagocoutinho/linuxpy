from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from linuxpy.device import BaseDevice, iter_device_files
from linuxpy.ioctl import ioctl
from linuxpy.types import PathLike
from linuxpy.util import make_find

from . import raw


@dataclass
class FixScreenInfo:
    name: str
    memory_start: int
    memory_size: int
    type: raw.Type
    type_aux: raw.Text
    visual: raw.Visual
    x_pan_step: int
    y_pan_step: int
    y_wrap_step: int
    line_size: int
    mmap_start: int
    mmap_size: int
    acceleration: raw.Acceleration
    capabilities: raw.Capability


def get_raw_fix_screen_info(fd) -> raw.fb_fix_screeninfo:
    return ioctl(fd, raw.IOC.GET_FSCREENINFO, raw.fb_fix_screeninfo())


def _translate_fix_fix_screen_info(screeninfo: raw.fb_fix_screeninfo):
    return FixScreenInfo(
        screeninfo.id.decode(),
        screeninfo.smem_start,
        screeninfo.smem_len,
        raw.Type(screeninfo.type),
        raw.Text(screeninfo.type_aux),
        raw.Visual(screeninfo.visual),
        screeninfo.xpanstep,
        screeninfo.ypanstep,
        screeninfo.ywrapstep,
        screeninfo.line_length,
        screeninfo.mmio_start,
        screeninfo.mmio_len,
        raw.Acceleration(screeninfo.accel),
        raw.Capability(screeninfo.capabilities),
    )


def get_fix_screen_info(fd) -> FixScreenInfo:
    info = get_raw_fix_screen_info(fd)
    return _translate_fix_fix_screen_info(info)


def get_raw_var_screen_info(fd) -> raw.fb_var_screeninfo:
    return ioctl(fd, raw.IOC.GET_VSCREENINFO, raw.fb_var_screeninfo())


def get_raw_colormap(fd):
    return ioctl(fd, raw.IOC.GETCMAP, raw.fb_cmap())


class Device(BaseDevice):
    PREFIX = "/dev/fb"

    def get_fix_screen_info(self):
        return get_fix_screen_info(self)


def iter_files(path: PathLike = "/dev") -> Iterable[Path]:
    """Returns an iterator over all frame buffer files"""
    return iter_device_files(path=path, pattern="fb*")


def iter_devices(path: PathLike = "/dev", **kwargs) -> Iterable[Device]:
    """Returns an iterator over all frame buffer devices"""
    return (Device(name, **kwargs) for name in iter_files(path=path))


find = make_find(iter_devices)
