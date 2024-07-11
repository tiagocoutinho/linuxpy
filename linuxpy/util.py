#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

"""Utility functions used by the library. Mostly for internal usage"""

import asyncio
import contextlib

from .types import Callable, Iterable, Iterator, Optional, Sequence, Union


def iter_chunks(lst: Sequence, size: int) -> Iterable:
    """
    Batch data from the sequence into groups of length n.
    The last batch may be shorter than size.
    """
    return (lst[i : i + size] for i in range(0, len(lst), size))


def chunks(lst: Sequence, size) -> tuple:
    """
    Batch data from the sequence into groups of length n.
    The last batch may be shorter than size.
    """
    return tuple(iter_chunks(lst, size))


def bcd_version_tuple(bcd: int) -> tuple[int, ...]:
    """Returns the tuple version of a BCD (binary-coded decimal) number"""
    text = f"{bcd:x}"
    text_size = len(text)
    if text_size % 2:
        text = "0" + text
    return tuple(int(i) for i in iter_chunks(text, 2))


def bcd_version(bcd: int) -> str:
    """Returns the text version of a BCD (binary-coded decimal) number"""
    return ".".join(str(i) for i in bcd_version_tuple(bcd))


@contextlib.contextmanager
def add_reader_asyncio(fd: int, callback: Callable[[], None], *args, loop: Optional[asyncio.AbstractEventLoop] = None):
    """Add reader during the context and remove it after"""
    if loop is None:
        loop = asyncio.get_event_loop()
    loop.add_reader(fd, callback, *args)
    try:
        yield loop
    finally:
        loop.remove_reader(fd)


def make_find(iter_devices: Callable[[], Iterator], needs_open=True) -> Callable:
    """
    Create a find function for the given callable. The callable should
    return an iterable where each element has the context manager capability
    (ie, it can be used in a with statement)
    """

    def find(find_all=False, custom_match=None, **kwargs):
        idevs = iter_devices()
        if kwargs or custom_match:

            def simple_accept(dev):
                result = all(getattr(dev, key) == value for key, value in kwargs.items())
                if result and custom_match:
                    return custom_match(dev)
                return result

            if needs_open:

                def accept(dev):
                    with dev:
                        return simple_accept(dev)
            else:
                accept = simple_accept

            idevs = filter(accept, idevs)
        return idevs if find_all else next(idevs, None)

    return find


class Version:
    """Simple version supporting only a.b.c format"""

    def __init__(self, major: int, minor: int, patch: int):
        self.major = major
        self.minor = minor
        self.patch = patch

    @classmethod
    def from_tuple(cls, sequence: Iterable[Union[str, int]]):
        """
        Create a Version from any sequence/iterable of 3 elements

        Examples that create a Version "3.2.1" object:
        ```python
        Version.from_tuple([3, 2, 1])
        Version.from_tuple(["3", 2, "1"])
        Version.from_tuple(range(3, 0, -1))

        # This will work although not recommended since it will not work
        # when any of the members is bigger than 9
        Version.from_tuple("321")
        ```
        """
        return cls(*map(int, sequence))

    @classmethod
    def from_str(cls, text):
        """
        Create a Version from text

        Example that create a Version "3.2.1" object:
        ```python
        Version.from_str("3.2.1")
        ```
        """
        return cls.from_tuple(text.split(".", 2))

    @classmethod
    def from_number(cls, number: int):
        """
        Create a Version from an integer where each member corresponds to
        one byte in the integer so that 0xFFFEFD corresponds to 255.254.253

        Example that create a Version "3.2.1" object:
        ```python
        Version.from_number((3<<16) + (2<<8) + 1)
        ```
        """
        return cls((number >> 16) & 0xFF, (number >> 8) & 0xFF, number & 0xFF)

    def __int__(self):
        return (self.major << 16) + (self.minor << 8) + self.patch

    def __repr__(self):
        return f"{self.major}.{self.minor}.{self.patch}"

    def __format__(self, fmt):
        return format(repr(self), fmt)

    def __getitem__(self, item):
        return self.tuple[item]

    def __eq__(self, other):
        return self.tuple == self._try_convert(other).tuple

    def __lt__(self, other):
        return self.tuple < self._try_convert(other).tuple

    def __le__(self, other):
        return self == other or self < other

    def __gt__(self, other):
        return not self <= other

    def __ge__(self, other):
        return not self < other

    @classmethod
    def _try_convert(cls, value):
        if isinstance(value, cls):
            return value
        elif isinstance(value, int):
            return cls.from_number(value)
        elif isinstance(value, str):
            return cls.from_str(value)
        elif isinstance(value, (tuple, list)):
            return cls.from_tuple(value)
        raise ValueError("Comparison with non-Version object")

    @property
    def tuple(self):
        """
        Returns a 3 element tuple representing the version
        so `Version(3,2,1).tuple()` yields the tuple `(3, 2, 1)`
        """
        return self.major, self.minor, self.patch


def bit_indexes(number):
    return [i for i, c in enumerate(bin(number)[:1:-1]) if c == "1"]
