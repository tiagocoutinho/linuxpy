#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import pytest

from linuxpy.util import Version, bcd_version, bcd_version_tuple, make_find, to_fd

bcd_expected = [
    (0x3, (3,)),
    (0x2549, (25, 49)),
    (0x999897, (99, 98, 97)),
    (0x123, (1, 23)),
    (0x12345, (1, 23, 45)),
]


@pytest.mark.parametrize("bcd, expected", bcd_expected)
def test_bcd_version_tuple(bcd, expected):
    assert bcd_version_tuple(bcd) == expected


@pytest.mark.parametrize("bcd, expected", bcd_expected)
def test_bcd_version(bcd, expected):
    assert bcd_version(bcd) == ".".join(map(str, expected))


def test_version():
    v = Version(4, 5, 6)
    assert v.major == 4
    assert v.minor == 5
    assert v.patch == 6
    assert int(v) == (4 << 16) + (5 << 8) + 6
    assert repr(v) == "4.5.6"
    assert v[0] == 4
    assert v[1] == 5
    assert v[2] == 6

    assert Version.from_number((4 << 16) + (5 << 8) + 6) == v
    assert Version.from_str("4.5.6") == v
    assert Version(4, 5, 5) < v
    assert Version(4, 5, 7) > v
    assert (4, 5, 7) > v
    assert (4, 5, 5) < v
    assert (4 << 16) + (5 << 8) + 5 < v

    # Provoke __gt__ to be called. ward makes some weird changes to assert x > y and
    # transforms it into x <= y!
    r = Version(4, 5, 7) > v
    assert r

    with pytest.raises(ValueError) as error:
        assert v > "hello"

    with pytest.raises(ValueError) as error:
        assert v < 56.7
    assert "Comparison with non-Version object" in error.value.args[0]


def test_make_find():
    class Device:
        def __init__(self, i):
            self.i = i

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return

    devices = [Device(a) for a in range(3)]

    def i():
        return iter(devices)

    find = make_find(i)

    assert find() is devices[0]
    assert find(i=1) is devices[1]
    assert find(custom_match=lambda device: device.i > 0) is devices[1]
    assert find(custom_match=lambda device: device.i > 2) is None
    assert len(tuple(find(find_all=True))) == 3
    assert all(a is b for a, b in zip(devices, find(find_all=True), strict=True))
    assert all(a is b for a, b in zip(devices[1:2], find(find_all=True, i=1), strict=True))
    assert all(
        a is b for a, b in zip(devices[1:3], find(find_all=True, custom_match=lambda device: device.i > 0), strict=True)
    )


def test_to_fd():
    class F:
        def __init__(self, fd):
            self.fd = fd

        def fileno(self):
            return self.fd

    assert to_fd(10) == 10
    assert to_fd(F(55)) == 55

    with pytest.raises(ValueError):
        to_fd(-1)

    with pytest.raises(ValueError):
        to_fd(F(-2))

    with pytest.raises(ValueError):
        to_fd("bla")
