#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import typing
import functools
import importlib
import os
import io
import select

StrOrBytesPath: typing.TypeAlias = str | bytes | os.PathLike[str] | os.PathLike[bytes]

FileDescriptorOrPath: typing.TypeAlias = int | StrOrBytesPath


def fopen(
        path: StrOrBytesPath,
        rw: bool = False,
        binary: bool = True,
        blocking: bool = False,
        close_on_exec: bool = True
    ) -> io.FileIO | io.TextIOWrapper:
    def opener(path, flags):
        if not blocking:
            flags |= os.O_NONBLOCK
        if close_on_exec:
            flags |= os.O_CLOEXEC
        return os.open(path, flags)

    kwargs = {"buffering": 0, "opener": opener}
    flgs = "rb" if binary else "r"
    if isinstance(rw, bool):
        flgs = "rb" if binary else "r"
        if rw:
            flgs += "+"
    else:
        flgs = rw
        if binary:
            flgs += "b"

    return open(path, flgs, **kwargs)


class IO:
    open = functools.partial(fopen, blocking=False)
    os = os
    select = select


class GeventModule:
    def __init__(self, name: str):
        self.name = name
        self._module = None

    @property
    def module(self):
        if self._module is None:
            self._module = importlib.import_module(f"gevent.{self.name}")
        return self._module

    def __getattr__(self, name: str):
        attr = getattr(self.module, name)
        setattr(self, name, attr)
        return attr


class GeventIO:
    @staticmethod
    def open(path: FileDescriptorOrPath, rw: bool = False, blocking: bool = False):
        mode = "rb+" if rw else "rb"
        import gevent.fileobject

        return gevent.fileobject.FileObject(path, mode, buffering=0)

    os = GeventModule("os")
    select = GeventModule("select")
