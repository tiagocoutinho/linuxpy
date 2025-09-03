#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

"""ioctl helper functions"""

import enum
import fcntl
import logging

from .ctypes import calcsize, i32, sizeof

NRBITS = 8
TYPEBITS = 8
SIZEBITS = 14
DIRBITS = 2

NRSHIFT = 0
TYPESHIFT = NRSHIFT + NRBITS
SIZESHIFT = TYPESHIFT + TYPEBITS
DIRSHIFT = SIZESHIFT + SIZEBITS

NONE = 0
WRITE = 1
READ = 2

log = logging.getLogger(__name__)


def IOC(direction, magic, number, size):
    """Generic IOC call"""
    if isinstance(magic, str):
        magic = ord(magic)
    if isinstance(size, str):
        size = calcsize(size)
    elif size is int:
        size = 4
    elif not isinstance(size, int):
        size = sizeof(size)
    return (
        i32(direction << DIRSHIFT).value
        | i32(magic << TYPESHIFT).value
        | i32(number << NRSHIFT).value
        | i32(size << SIZESHIFT).value
    )


def IO(magic, number):
    return IOC(NONE, magic, number, 0)


def IOW(magic, number, size):
    return IOC(WRITE, magic, number, size)


def IOR(magic, number, size):
    return IOC(READ, magic, number, size)


def IOWR(magic, number, size):
    return IOC(READ | WRITE, magic, number, size)


def ioctl(fd, request, *args):
    req = request.name if isinstance(request, enum.Enum) else request
    log.debug("request=%s, arg=%s", req, args)
    fcntl.ioctl(fd, request, *args)
    return args and args[0] or None
