#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import asyncio
import contextlib

from .types import Callable, Iterator, Optional


def ichunks(lst, size):
    return (lst[i : i + size] for i in range(0, len(lst), size))


def chunks(lst, size) -> tuple:
    return tuple(ichunks(lst, size))


def bcd_version_tuple(bcd: int) -> tuple:
    text = hex(bcd)[2:]
    if len(text) % 2:
        text = "0" + text
    return tuple(int(i) for i in ichunks(text, 2))


def bcd_version(bcd: int) -> str:
    return ".".join(str(i) for i in bcd_version_tuple(bcd))


@contextlib.contextmanager
def add_reader_asyncio(fd: int, callback: Callable[[], None], *args, loop: Optional[asyncio.AbstractEventLoop] = None):
    """Add reader during the context and remove it after"""
    if loop is None:
        loop = asyncio.get_event_loop()
    loop.add_reader(fd, callback, *args)
    try:
        yield loop
    finally:
        loop.remove_reader(fd)


def make_find(iter_devices: Callable[[], Iterator]) -> Callable:
    def find(find_all=False, custom_match=None, **kwargs):
        idevs = iter_devices()
        if custom_match:
            idevs = filter(custom_match, idevs)
        if kwargs:

            def accept(d):
                return all(getattr(d, key) == value for key, value in kwargs.items())

            idevs = filter(accept, idevs)
        return idevs if find_all else next(idevs, None)

    return find
