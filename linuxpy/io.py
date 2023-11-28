#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import functools
import os
import select


def fopen(path, rw=False, binary=True, blocking=False, close_on_exec=True):
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
    select = select.select


class GeventIO:
    @staticmethod
    def open(path, rw=False):
        mode = "rb+" if rw else "rb"
        import gevent.fileobject

        return gevent.fileobject.FileObject(path, mode, buffering=0)

    @staticmethod
    def select(*args, **kwargs):
        import gevent.select

        return gevent.select.select(*args, **kwargs)
