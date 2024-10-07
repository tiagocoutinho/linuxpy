#
# This file is part of the linuxpy project
#
# Copyright (c) 2024 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import functools
from pathlib import Path

from .proc import PROC_PATH
from .types import Generator, NamedTuple, Optional

MOUNTS_PATH: Path = PROC_PATH / "mounts"


class MountInfo(NamedTuple):
    dev_type: str
    mount_point: str
    fs_type: str
    attrs: list[str]


def gen_read() -> Generator[MountInfo, None, None]:
    data = MOUNTS_PATH.read_text()
    for line in data.splitlines():
        dev_type, mount_point, fs_type, attrs, *_ = line.split()
        yield MountInfo(dev_type, mount_point, fs_type, attrs.split(","))


@functools.cache
def cache() -> tuple[MountInfo, ...]:
    return tuple(gen_read())


@functools.cache
def get_mount_point(dev_type, fs_type=None) -> Optional[Path]:
    if fs_type is None:
        fs_type = dev_type
    for _dev_type, mount_point, _fs_type, *_ in cache():
        if dev_type == _dev_type and fs_type == _fs_type:
            return Path(mount_point)


def sysfs() -> Optional[Path]:
    return get_mount_point("sysfs")


def configfs() -> Optional[Path]:
    return get_mount_point("configfs")
