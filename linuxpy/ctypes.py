#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import collections
import ctypes
import struct
import time

from .constants import MICROSEC_PER_SEC, NANOSEC_PER_MICROSEC

i8 = ctypes.c_int8
i16 = ctypes.c_int16
i32 = ctypes.c_int32
i64 = ctypes.c_int64

u8 = ctypes.c_uint8
u16 = ctypes.c_uint16
u32 = ctypes.c_uint32
u64 = ctypes.c_uint64


cint = ctypes.c_int
cuint = ctypes.c_uint
clong = ctypes.c_long
culong = ctypes.c_ulong
clonglong = ctypes.c_longlong
culonglong = ctypes.c_ulonglong

cchar = ctypes.c_char
ccharp = ctypes.c_char_p

cenum = cuint
cvoidp = ctypes.c_void_p

fsword = cuint
fsblkcnt = culong
fsfilcnt = culong

cast = ctypes.cast
sizeof = ctypes.sizeof
byref = ctypes.byref

calcsize = struct.calcsize

Union = ctypes.Union

pointer = ctypes.pointer
POINTER = ctypes.POINTER

create_string_buffer = ctypes.create_string_buffer
cast = ctypes.cast
memmove = ctypes.memmove


def memcpy(dst, src):
    typ = type(dst)
    return memmove(byref(dst), byref(src), sizeof(typ))


class Struct(ctypes.Structure):
    def __repr__(self):
        name = type(self).__name__
        fields = filter(lambda field: field[0] != "reserved", self._fields_)
        fields = ", ".join(f"{field[0]}={getattr(self, field[0])}" for field in fields)
        return f"{name}({fields})"

    def __iter__(self):
        for fname, ftype in self._fields_:
            yield fname, ftype, getattr(self, fname)

    def asdict(self):
        r = collections.OrderedDict()
        for name, _, value in self:
            if hasattr(value, "_fields_"):
                value = value.asdict()
            r[name] = value
        return r


class timeval(Struct):
    _fields_ = [
        ("secs", ctypes.c_long),
        ("usecs", ctypes.c_long),
    ]

    def set_ns(self, value=None):
        if value is None:
            value = time.time_ns()
        microsecs = time.time_ns() // NANOSEC_PER_MICROSEC
        self.secs = microsecs // MICROSEC_PER_SEC
        self.usecs = microsecs % MICROSEC_PER_SEC


class timespec(Struct):
    _fields_ = [
        ("secs", ctypes.c_long),
        ("nsecs", ctypes.c_long),
    ]

    def timestamp(self):
        return self.secs + self.nsecs * 1e-9


c = ctypes.cdll.LoadLibrary("libc.so.6")
