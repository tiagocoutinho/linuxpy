#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

"""Utility functions used by the library. Mostly for internal usage"""

import asyncio
import contextlib
import functools
import random
import selectors
import string

from .types import (
    AsyncIterator,
    Callable,
    Collection,
    FDLike,
    Iterable,
    Iterator,
    Optional,
    Sequence,
    T,
    Union,
)


def iter_chunks(lst: Sequence, size: int) -> Iterable:
    """
    Batch data from the sequence into groups of length n.
    The last batch may be shorter than size.
    """
    return (lst[i : i + size] for i in range(0, len(lst), size))


def chunks(lst: Sequence, size: int) -> tuple:
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


def to_fd(fd: FDLike):
    """Return a file descriptor from a file object.

    Parameters:
    fd -- file object or file descriptor

    Returns:
    corresponding file descriptor

    Raises:
    ValueError if the object is invalid
    """
    if not isinstance(fd, int):
        try:
            fd = int(fd.fileno())
        except (AttributeError, TypeError, ValueError):
            raise ValueError(f"Invalid file object: {fd!r}") from None
    if fd < 0:
        raise ValueError(f"Invalid file descriptor: {fd}")
    return fd


int16 = functools.partial(int, base=16)


def try_numeric(text: str):
    """
    Try to translate given text into int, int base 16 or float.
    Returns the orig and return the original text if it fails.

    Args:
        text (str): text to be translated

    Returns:
        int, float or str: The converted text
    """
    for func in (int, int16, float):
        try:
            return func(text)
        except ValueError:
            pass
    return text


@contextlib.contextmanager
def add_reader_asyncio(fd: FDLike, callback: Callable, *args, loop: Optional[asyncio.AbstractEventLoop] = None):
    """Add reader during the context and remove it after"""
    fd = to_fd(fd)
    if loop is None:
        loop = asyncio.get_event_loop()
    loop.add_reader(fd, callback, *args)
    try:
        yield loop
    finally:
        loop.remove_reader(fd)


async def astream(fd: FDLike, read_func: Callable, max_buffer_size=10) -> AsyncIterator:
    queue = asyncio.Queue(maxsize=max_buffer_size)

    def feed():
        queue.put_nowait(read_func())

    with add_reader_asyncio(fd, feed):
        while True:
            event = await queue.get()
            yield event


def Selector(fds: Collection[FDLike], events=selectors.EVENT_READ) -> selectors.DefaultSelector:
    """A selectors.DefaultSelector with given fds registered"""
    selector = selectors.DefaultSelector()
    for fd in fds:
        selector.register(fd, events)
    return selector


SelectorEventMask = int
SelectorEvent = tuple[selectors.SelectorKey, SelectorEventMask]


def selector_stream(selector: selectors.BaseSelector, timeout: Optional[float] = None) -> Iterable[SelectorEvent]:
    """A stream of selector read events"""
    while True:
        yield from selector.select(timeout)


def selector_file_stream(fds: Collection[FDLike], timeout: Optional[float] = None) -> Iterable[SelectorEvent]:
    """An inifinte stream of selector read events"""
    yield from selector_stream(Selector(fds), timeout)


def file_stream(fds: Collection[FDLike], timeout: Optional[float] = None) -> Iterable[FDLike]:
    """An infinite stream of read ready file descriptors"""
    yield from (key.fileobj for key, _ in selector_file_stream(fds, timeout))


def event_stream(fds: Collection[FDLike], read: Callable[[FDLike], T], timeout: Optional[float] = None) -> Iterable[T]:
    """An infinite stream of events. The given read callable is called for each file
    that is reported as ready"""
    yield from (read(fd) for fd in file_stream(fds))


async def async_selector_stream(selector: selectors.BaseSelector) -> AsyncIterator[SelectorEvent]:
    """An asyncronous infinite stream of selector read events"""
    stream = astream(selector, selector.select)
    try:
        async for events in stream:
            for event in events:
                yield event
    finally:
        await stream.aclose()


async def async_selector_file_stream(fds: Collection[FDLike]) -> AsyncIterator[SelectorEvent]:
    """An asyncronous infinite stream of selector read events"""
    selector = Selector(fds)
    stream = async_selector_stream(selector)
    try:
        async for event in stream:
            yield event
    finally:
        await stream.aclose()


async def async_file_stream(fds: Collection[FDLike]) -> AsyncIterator[FDLike]:
    """An asyncronous infinite stream of read ready files"""
    stream = async_selector_file_stream(fds)
    try:
        async for key, _ in stream:
            yield key.fileobj
    finally:
        await stream.aclose()


async def async_event_stream(fds: Collection[FDLike], read: Callable[[FDLike], T]):
    """An asyncronous stream of events. The given read callable is called for each file
    that is reported as ready"""
    stream = async_file_stream(fds)
    try:
        async for fd in stream:
            yield read(fd)
    finally:
        await stream.aclose()


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


def bit_indexes(number: int) -> list[int]:
    """
    Return the list of indexes that have an active bit on the number.

    Example bit_indexes(74) gives [1, 3, 6] (74 == 0b1001010)
    """
    return [i for i, c in enumerate(bin(number)[:1:-1]) if c == "1"]


ascii_alphanumeric = string.ascii_letters + string.digits


def random_name(min_length=32, max_length=32):
    """
    Generates a random name like text of ascii characters (letters or digits).

    The first character is always a letter
    """
    if not (k := random.randint(min_length, max_length)):
        return ""
    first = random.choice(string.ascii_letters)
    return first + "".join(random.choices(ascii_alphanumeric, k=k - 1))
