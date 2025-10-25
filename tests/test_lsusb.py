#
# This file is part of the linuxpy project
#
# Copyright (c) 2025 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.


import re

import linuxpy.usb.lsusb

LS_REG_EXP = re.compile(r"Bus \d{3} Device \d{3}: ID [0-9a-f]{4}:[0-9a-f]{4}")


def test_lsusb(capsys):
    linuxpy.usb.lsusb.lsusb()
    result = capsys.readouterr()
    assert not result.err
    for line in result.out.splitlines():
        assert LS_REG_EXP.match(line)
