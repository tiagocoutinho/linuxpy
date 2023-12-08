#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import contextlib
import logging
import os
import pathlib
from io import IOBase

from .io import IO

DEV_PATH = pathlib.Path("/dev")


log = logging.getLogger(__name__)


class ReentrantOpen(contextlib.AbstractContextManager):
    def __init__(self):
        self._context_level = 0

    def __enter__(self):
        if not self._context_level:
            self.open()
        self._context_level += 1
        return self

    def __exit__(self, *exc):
        self._context_level -= 1
        if not self._context_level:
            self.close()

    def open(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError


def device_number(path):
    """Retrieves device"""
    num = ""
    for c in str(path)[::-1]:
        if c.isdigit():
            num = c + num
        else:
            break
    return int(num) if num else None


def is_device_file(path, read_write=True):
    """Check if path is a readable (and, optionally, writable) character device."""
    path = pathlib.Path(path)
    if not path.is_char_device():
        return False
    access = os.R_OK | (os.W_OK if read_write else 0)
    if not os.access(str(path), access):
        return False
    return True


def iter_device_files(path="/dev", pattern="*"):
    path = pathlib.Path(path)
    items = path.glob(pattern)

    return filter(is_device_file, items)


class BaseDevice(ReentrantOpen):
    PREFIX = None

    def __init__(self, name_or_file, read_write=True, io=IO):
        super().__init__()
        self.io = io
        if isinstance(name_or_file, (str, pathlib.Path)):
            filename = pathlib.Path(name_or_file)
            self._read_write = read_write
            self._fobj = None
        elif isinstance(name_or_file, IOBase):
            filename = pathlib.Path(name_or_file.name)
            self._read_write = "+" in name_or_file.mode
            self._fobj = name_or_file
            # this object context manager won't close the file anymore
            self._context_level += 1
            self._on_open()
        else:
            raise TypeError(
                f"name_or_file must be a Path, str or a file-like object, not {name_or_file.__class__.__name__}"
            )
        self.log = log.getChild(filename.stem)
        self.filename = filename
        self.index = device_number(filename)

    def __repr__(self):
        return f"<{type(self).__name__} name={self.filename}, closed={self.closed}>"

    def _on_open(self):
        pass

    def _on_close(self):
        pass

    @classmethod
    def from_id(cls, did: int, **kwargs):
        return cls(f"{cls.PREFIX}{did}", **kwargs)

    def open(self):
        if not self._fobj:
            self.log.info("opening %s", self.filename)
            self._fobj = self.io.open(self.filename, self._read_write)
            self._on_open()
            self.log.info("opened %s", self.filename)

    def close(self):
        if not self.closed:
            self._on_close()
            self.log.info("closing %s", self.filename)
            self._fobj.close()
            self._fobj = None
            self.log.info("closed %s", self.filename)

    def fileno(self):
        return self._fobj.fileno()

    @property
    def closed(self):
        return self._fobj is None or self._fobj.closed

    @property
    def is_blocking(self):
        return os.get_blocking(self.fileno())
