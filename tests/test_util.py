#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

from ward import raises, test

from linuxpy.util import Version


@test("version")
def _():
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

    with raises(ValueError) as error:
        assert v > "hello"

    with raises(ValueError) as error:
        assert v < 56.7
    assert "Comparison with non-Version object" in error.raised.args[0]
