import re

import linuxpy.usb.lsusb

LS_REG_EXP = re.compile(r"Bus \d{3} Device \d{3}: ID [0-9a-f]{4}:[0-9a-f]{4}")


def test_lsusb(capsys):
    linuxpy.usb.lsusb.lsusb()
    result = capsys.readouterr()
    assert not result.err
    for line in result.out.splitlines():
        assert LS_REG_EXP.match(line)
