#
# This file is part of the python-linux project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import functools
import os
import select


def fopen(path, rw=False, binary=True, blocking=False):
    kwargs = {"buffering": 0}
    if not blocking:

        def opener(path, flags):
            return os.open(path, flags | os.O_NONBLOCK)

        kwargs["opener"] = opener
    flags = "rb" if binary else "r"
    if rw:
        flags += "+"
    return open(path, flags, **kwargs)


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
