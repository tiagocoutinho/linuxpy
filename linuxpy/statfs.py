#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import enum
import functools

from .ctypes import (
    POINTER,
    Struct,
    c,
    ccharp,
    cint,
    cuint,
    culong,
    fsblkcnt,
    fsfilcnt,
    pointer,
)
from .magic import Magic


class fsid(Struct):
    _fields_ = [("val", cint * 2)]


class statfs(Struct):
    _fields_ = [
        ("f_type", cuint),  # Type of filesystem (see below)
        ("f_bsize", cuint),  # Optimal transfer block size
        ("f_blocks", fsblkcnt),  # Total data blocks in filesystem
        ("f_bfree", fsblkcnt),  # Free blocks in filesystem
        ("f_bavail", fsblkcnt),  # Free blocks available to unprivileged user
        ("f_files", fsfilcnt),  # Total file nodes in filesystem
        ("f_ffree", fsfilcnt),  # Free file nodes in filesystem
        ("f_fsid", fsid),  # Filesystem ID
        ("f_namelen", cuint),  # Maximum length of filenames
        ("f_frsize", cuint),  # Fragment size (since Linux 2.6)
        ("f_flags", cuint),  # Mount flags of filesystem (since Linux 2.6.36)
        # Setting f_spare to 4 * int was giving me segfault
        ("f_spare", cuint * 16),  # Padding bytes reserved for future use
    ]


class statvfs(Struct):
    _fields_ = [
        ("f_bsize", culong),  # Filesystem block size
        ("f_frsize", culong),  # Fragment size
        ("f_blocks", fsblkcnt),  # Size of fs in f_frsize units
        ("f_bfree", fsblkcnt),  # Number of free blocks
        ("f_bavail", fsblkcnt),  # Number of free blocks for unprivileged user
        ("f_files", fsfilcnt),  # Number of inodes
        ("f_ffree", fsfilcnt),  # Number of free inodes
        ("f_favail", fsfilcnt),  # Number of free inodes for unprivileged user
        ("f_fsid", culong),  # Filesystem ID
        ("f_flag", culong),  # Mount flags
        ("f_namemax", culong),  # Maximum filename length
    ]


class Flag(enum.IntFlag):
    RDONLY = 0x0001  # mount read-only
    NOSUID = 0x0002  # ignore suid and sgid bits
    NODEV = 0x0004  # disallow access to device special files
    NOEXEC = 0x0008  # disallow program execution
    SYNCHRONOUS = 0x0010  # writes are synced at once
    VALID = 0x0020  # f_flags support is implemented
    MANDLOCK = 0x0040  # allow mandatory locks on an FS
    # 0x0080 used for ST_WRITE in glibc
    # 0x0100 used for ST_APPEND in glibc
    # 0x0200 used for ST_IMMUTABLE in glibc
    NOATIME = 0x0400  # do not update access times
    NODIRATIME = 0x0800  # do not update directory access times
    RELATIME = 0x1000  # update atime relative to mtime/ctime
    NOSYMFOLLOW = 0x2000  # do not follow symlinks


c.statfs.argtypes = [ccharp, POINTER(statfs)]
c.statfs.restype = cint

c.statvfs.argtypes = [ccharp, POINTER(statvfs)]
c.statvfs.restype = cint


def get_statfs_raw(path) -> statfs:
    if not isinstance(path, (bytes, ccharp)):
        path = str(path).encode()
    result = statfs()
    c.statfs(path, pointer(result))
    return result


@functools.lru_cache
def get_fs_type(path) -> Magic:
    ftype = get_statfs_raw(path).f_type
    return None if not ftype else Magic(ftype)
