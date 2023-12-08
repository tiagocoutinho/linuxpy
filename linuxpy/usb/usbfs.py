#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import collections
import functools
import struct

from .base import USB_DEV_PATH, USB_DEV_TMPFS_PATH, BaseDevice

USBFS_MAXDRIVERNAME = 255


DeviceDescriptorDecoder = struct.Struct("<BBHBBBBHHHBBBB")
DeviceDescriptor = collections.namedtuple(
    "DeviceDescriptor",
    (
        "length",
        "descriptor_type",
        "bcdUSB",
        "device_class",
        "device_sub_class",
        "protocol",
        "max_pack_size",
        "vendor_id",
        "product_id",
        "bcdDevice",
        "manufacturer",
        "product_index",
        "serial_number_index",
        "nb_configs",
    ),
)


def read_descriptor(fd):
    # just after the open() call we can read the ubfs device descriptor
    # it will contain at least 18 bytes with basic usb device information
    data = fd.read(256)
    return DeviceDescriptor(*DeviceDescriptorDecoder.unpack_from(data))


class Device(BaseDevice):
    def __init__(self, path):
        super().__init__(path)
        self.descriptor = None

    @functools.cached_property
    def bus_number(self):
        return int(self.filename.parent.name)

    @functools.cached_property
    def device_address(self):
        return int(self.filename.name)

    @functools.cached_property
    def session_id(self):
        return self.bus_number << 8 | self.device_address

    @property
    def vendor_id(self):
        return self.descriptor.vendor_id

    @property
    def product_id(self):
        return self.descriptor.product_id

    @property
    def manufacturer(self):
        return self.descriptor.manufacturer

    def open(self):
        self._fobj = open(self.filename, "rb")
        self.descriptor = read_descriptor(self._fobj)


@functools.cache
def usbfs_path():
    for path in (USB_DEV_TMPFS_PATH, USB_DEV_PATH):
        if path.is_dir():
            # assume if we find any files that it must be the right place
            if next(path.iterdir(), None):
                return path

    # On udev based systems without any usb-devices /dev/bus/usb will not
    # exist. So if we've not found anything and we're using udev for hotplug
    # simply assume /dev/bus/usb rather then making this fail
    return USB_DEV_TMPFS_PATH


def iter_paths():
    for path in usbfs_path().iterdir():
        try:
            int(path.name)
        except ValueError:
            continue
        for sub_path in path.iterdir():
            try:
                int(sub_path.name)
            except ValueError:
                continue
            yield sub_path


def iter_devices():
    for path in iter_paths():
        yield Device(path)


def lsusb():
    for dev in iter_devices():
        dev.open()
