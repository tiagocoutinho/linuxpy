#
# This file is part of the linuxpy project
#
# Copyright (c) 2025 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import errno
import select
import socket

from linuxpy.ctypes import cast, create_string_buffer, cvoidp, pointer, sizeof
from linuxpy.device import ReentrantOpen
from linuxpy.ioctl import ioctl

from . import raw


def get_range(fd, ifname):
    req = raw.iwreq()
    req.ifr_ifrn.ifrn_name = ifname.encode()

    result = raw.iw_range()
    req.u.data.pointer = cast(pointer(result), cvoidp)
    req.u.data.length = sizeof(result)
    ioctl(fd, raw.IOC.GIWRANGE, req)
    return result


def start_scan(fd, ifname):
    req = raw.iwreq()
    req.ifr_ifrn.ifrn_name = ifname.encode()
    try:
        ioctl(fd, raw.IOC.SIWSCAN, req)
    except OSError as error:
        if error.errno != errno.EPERM:
            raise
    return req


def iter_get_scan(fd, ifname):
    req = raw.iwreq()
    req.ifr_ifrn.ifrn_name = ifname.encode()

    data = create_string_buffer(16 * 1024)
    req.u.data.pointer = cast(data, cvoidp)
    req.u.data.length = 16 * 1024
    ioctl(fd, raw.IOC.GIWSCAN, req)
    size = req.u.data.length
    assert size
    offset = 0
    while True:
        if offset + 4 > size:
            break
        evt = raw.iw_event.from_buffer(data, offset)
        offset += evt.len
        yield evt


def get_scan(fd, ifname):
    result = {}
    for event in iter_get_scan(fd, ifname):
        cmd = event.cmd
        print(hex(cmd), event.len)
        if cmd == raw.IOC.GIWAP:
            result["address"] = event.u.ap_addr.sa_data

        elif cmd == raw.IOC.GIWFREQ:
            result["frequency"] = event.u.freq.m * 10**event.u.freq.e
        elif cmd == raw.EventType.QUAL:
            result["quality"] = event.u.qual.qual
            result["level"] = event.u.qual.level
            result["noise"] = event.u.qual.noise
        elif cmd == raw.IOC.GIWRATE:
            result.setdefault("bit_rates", []).append(event.u.bitrate.value)
        elif cmd == raw.IOC.GIWENCODE:
            ...
        elif cmd == raw.IOC.GIWESSID:
            ...
        elif cmd == raw.IOC.GIWMODE:
            ...
        elif cmd == raw.EventType.CUSTOM:
            print("Custom!")
            ...
        else:
            print(hex(cmd))
    return result


def wait_scan(fd):
    return select.select((fd,), (), ())


class Wireless(ReentrantOpen):
    def __init__(self):
        super().__init__()
        self._fobj = None

    def open(self):
        self._fobj = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_IP)

    def close(self):
        if self._fobj is None:
            return
        self._fobj.close()
        self._fobj = None

    def fileno(self):
        return -1 if self._fobj is None else self._fobj.fileno()

    def scan(self, ifname):
        start_scan(self, ifname)
        return get_scan(self, ifname)
