#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import collections.abc
import os
import pathlib
import typing

if hasattr(typing, "Self"):  # 3.11+
    Self = typing.Self
else:
    import typing_extensions

    Self = typing_extensions.Self

if hasattr(collections.abc, "Buffer"):  # 3.12+
    Buffer = collections.abc.Buffer
else:
    import typing_extensions

    Buffer = typing_extensions.Buffer

if hasattr(typing, "TypeAlias"):  # 3.11+
    TypeAlias = typing.TypeAlias
else:
    import typing_extensions

    TypeAlias = typing_extensions.TypeAlias

Union = typing.Union
Optional = typing.Optional
PathLike = Union[str, pathlib.Path, os.PathLike]


class HasFileno(typing.Protocol):
    def fileno(self) -> int: ...


FD = int
FDLike = Union[FD, HasFileno]


Iterable = collections.abc.Iterable
Iterator = collections.abc.Iterator
AsyncIterable = collections.abc.AsyncIterable
AsyncIterator = collections.abc.AsyncIterator
Generator = typing.Generator
Callable = collections.abc.Callable
Sequence = collections.abc.Sequence
Collection = collections.abc.Collection
NamedTuple = typing.NamedTuple

T = typing.TypeVar("T")
