#
# This file is part of the linuxpy project
#
# Copyright (c) 2025 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import socket

from linuxpy.ctypes import create_string_buffer, sizeof
from linuxpy.ioctl import ioctl

from . import raw

MAX_INTERFACES = 1024
IFNAME_SIZE = 16


def get_ifnames():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    req = raw.ifconf()
    # first ioctl call to get the necessary size
    ioctl(sock, raw.IOC.GIFCONF, req)
    size = req.ifc_len
    data = create_string_buffer(2 * size)
    req.ifc_ifcu.ifcu_buf = data
    ioctl(sock, raw.IOC.GIFCONF, req)
    n = req.ifc_len // sizeof(raw.ifreq)
    return [req.ifc_ifcu.ifcu_req[i].ifr_ifrn.ifrn_name.decode() for i in range(n)]
