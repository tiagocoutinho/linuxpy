#
# This file is part of the linuxpy project
#
# Copyright (c) 2024 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import pathlib

from linuxpy.codegen.base import CEnum, run

HEADERS = [
    "/usr/include/linux/spi/spi.h",
    "/usr/include/linux/spi/spidev.h",
]


TEMPLATE = """\
#
# This file is part of the linuxpy project
#
# Copyright (c) 2024 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

# This file has been generated by {name}
# Date: {date}
# System: {system}
# Release: {release}
# Version: {version}

import enum

from linuxpy.ioctl import IOR as _IOR, IOW as _IOW, IOWR as _IOWR
from linuxpy.ctypes import u8, u16, u32, cuint, cint, cchar, culonglong
from linuxpy.ctypes import Struct, Union, POINTER, cvoidp


{enums_body}


{structs_body}


{iocs_body}"""


class Mode32(CEnum):
    def add_item(self, name, value):
        if "_BITUL" in value:
            value = value.replace("_BITUL(", "").replace(")", "")
            value = f"1 << {value}"
        super().add_item(name, value)


# macros from #define statements
MACRO_ENUMS = [
    CEnum("IOC", "SPI_IOC_"),
    Mode32("Mode32", "SPI_", klass="IntFlag", filter=lambda k, v: "MASK" not in k),
]


this_dir = pathlib.Path(__file__).parent


def main(output=this_dir.parent / "spi" / "raw.py"):
    run(__name__, HEADERS, TEMPLATE, MACRO_ENUMS, output=output)


if __name__ == "__main__":
    main()