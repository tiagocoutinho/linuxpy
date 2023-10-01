
# run with:
# 

import pathlib
import pprint
import datetime
import platform

import requests

this_dir = pathlib.Path(__file__).parent


USB_IDS = "http://www.linux-usb.org/usb.ids"


def get_raw(url: str = USB_IDS) -> str:
    response = requests.get(url)
    response.raise_for_status()
    return response.text


def get(url: str = USB_IDS) -> dict[int, ]:
    raw = get_raw(url=url)

    items = {}

    for line in raw.splitlines():
        if line.startswith("#"):
            continue
        if line.startswith("\t\t"):  # Interface, protocol, etc
            l2_id, l2_name  = line.strip().split("  ", 1)
            l2_id = int(l2_id, 16)
            l2 = {"name": l2_name}
            l1.setdefault("children", {})[l2_id] = l2
        elif line.startswith("\t"):  # Device, subclass
            l1_id, l1_name = line.strip().split("  ", 1)
            l1_id = int(l1_id, 16)
            l1 = {"name": l1_name}
            l0.setdefault("children", {})[l1_id] = l1
        elif line: # Vendor, class, audio terminal, etc 
            l0_id, l0_name = line.split("  ", 1)
            if ' ' in l0_id:
                itype, l0_id = l0_id.split(' ', 1)
            else:
                itype = 'V' # Vendors don't have prefix
            l0_id = int(l0_id, 16)
            l0 = {"name": l0_name}
            items.setdefault(itype, {})[l0_id] = l0

    return items


HEADER = """\
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

# This file has been generated by {name}
# Date: {date}
# System: {system}
# Release: {release}
# Version: {version}

"""


def dump_items(items, path = this_dir.parent / "usb" / "usbids.py"):
    path = pathlib.Path(path)
    fields = {
        "name": 'linuxpy.codegen.usbids',
        "date": datetime.datetime.now(),
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
    }
    text = HEADER.format(**fields)

    with path.open("w") as fobj:
        fobj.write(text)
        for item, values in items.items():
            fobj.write(f"{item} = {pprint.pformat(values)}\n\n\n")


def main():
    items = get()
    dump_items(items)


if __name__ == "__main__":
    main()