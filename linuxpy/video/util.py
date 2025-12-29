#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.


import typing

CharType: typing.TypeAlias = str | bytes


def v4l2_fourcc(a: CharType, b: CharType, c: CharType, d: CharType):
    return ord(a) | (ord(b) << 8) | (ord(c) << 16) | (ord(d) << 24)


def v4l2_fourcc_be(a: CharType, b: CharType, c: CharType, d: CharType):
    return (v4l2_fourcc(a, b, c, d)) | (1 << 31)
