#
# This file is part of the linuxpy project
#
# Copyright (c) 2025 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import errno
import socket

from linuxpy.ctypes import cast, create_string_buffer, cvoidp, pointer, sizeof
from linuxpy.device import ReentrantOpen
from linuxpy.ioctl import ioctl

from . import raw


def get_range(fd, ifname) -> raw.iw_range:
    req = raw.iwreq()
    req.ifr_ifrn.ifrn_name = ifname.encode()

    result = raw.iw_range()
    req.u.data.pointer = cast(pointer(result), cvoidp)
    req.u.data.length = sizeof(result)
    ioctl(fd, raw.IOC.GIWRANGE, req)
    return result


def start_scan(fd, ifname) -> raw.iwreq:
    req = raw.iwreq()
    req.ifr_ifrn.ifrn_name = ifname.encode()
    req.u.data.flags = raw.ScanFlag.ALL_ESSID
    try:
        ioctl(fd, raw.IOC.SIWSCAN, req)
    except OSError as error:
        if error.errno != errno.EPERM:
            raise
    return req


def decode_quality(value, flags):
    if raw.StatsFlag.DBM in flags:
        if value >= 64:
            value -= 0x100
        return {"value": value, "unit": "dBm"}
    elif raw.StatsFlag.RCPI in flags:
        return {"value": value / 2 - 110, "unit": "dBm"}
    return {"value": value}


def decode_event(data, offset):
    event = raw.iw_event.from_buffer(data, offset)
    cmd = command(event.cmd)
    result = {}
    if cmd == raw.IOC.GIWAP:
        result["address"] = {"value": event.u.ap_addr.sa_data[:6]}
    elif cmd == raw.IOC.GIWFREQ:
        value = frequency(event.u.freq)
        if value < 1000:
            result["channel"] = {"value": value}
        else:
            result["frequency"] = {"value": value, "unit": "Hz"}
    elif cmd == raw.IOC.GIWRATE:
        param_size = sizeof(raw.iw_param)
        value = [
            raw.iw_param.from_buffer_copy(data, start).value
            for start in range(offset + 8, offset + event.len, param_size)
        ]
        result["bit_rates"] = {"value": value, "unit": "b/s"}
    elif cmd == raw.IOC.GIWESSID:
        result["essid"] = {"value": data[offset + 16 : offset + event.len].decode()}
    elif cmd == raw.IOC.GIWMODE:
        result["mode"] = {"value": raw.OperationMode(event.u.mode)}
    elif cmd == raw.EventType.QUAL:
        flag = raw.StatsFlag(event.u.qual.updated)
        if raw.StatsFlag.QUAL_INVALID not in flag:
            result["quality"] = {"value": event.u.qual.qual}
        if raw.StatsFlag.LEVEL_INVALID not in flag:
            result["level"] = decode_quality(event.u.qual.level, flag)
        if raw.StatsFlag.NOISE_INVALID not in flag:
            result["noise"] = decode_quality(event.u.qual.noise, flag)
    elif cmd == raw.EventType.CUSTOM:
        result["extra"] = {"value": data[offset + 16 : offset + event.len].decode()}
    elif cmd == raw.IOC.GIWENCODE:
        print(cmd.name)
    elif cmd == raw.EventType.GENIE:
        print(cmd.name)
    else:
        print(cmd.name)
    return event, result


def iter_get_scan(fd, ifname):
    req = raw.iwreq()
    req.ifr_ifrn.ifrn_name = ifname.encode()

    SIZE = 16 * 1024
    data = create_string_buffer(SIZE)
    req.u.data.pointer = cast(data, cvoidp)
    req.u.data.length = SIZE
    ioctl(fd, raw.IOC.GIWSCAN, req)
    offset, size = 0, req.u.data.length
    custom = 0
    while True:
        if offset + 4 > size:
            break
        event, result = decode_event(data, offset)
        if "extra" in result:
            result[f"extra_{custom}"] = result.pop("extra")
            custom += 1
        yield result
        offset += event.len


def command(i):
    try:
        return raw.IOC(i)
    except ValueError:
        return raw.EventType(i)


def frequency(freq: raw.iw_freq) -> float:
    return freq.m * 10**freq.e


def get_scan(fd, ifname):
    result = {}
    for event in iter_get_scan(fd, ifname):
        result.update(event)
    return result


class Wireless(ReentrantOpen):
    def __init__(self):
        super().__init__()
        self._fobj = None

    def open(self):
        self._fobj = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_IP)
        self._fobj.setblocking(False)

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
