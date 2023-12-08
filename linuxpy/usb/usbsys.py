#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import enum
import functools
import pathlib

from .. import sysfs
from ..ctypes import sizeof
from ..util import bcd_version, make_find
from . import raw
from .base import USB_DEV_TMPFS_PATH, BaseDevice, DescriptorType

Speed = raw.UsbDeviceSpeed


class Removable(enum.Enum):
    UNKNOWN = "unknown"
    FIXED = "fixed"
    REMOVABLE = "removable"


def _attr_getter(filename, decode, alternative):
    def getter(self):
        path = self.syspath / filename
        if path.exists():
            with path.open() as fobj:
                return decode(fobj.read())
        elif alternative:
            return alternative(self)

    return getter


def cached_attr(filename, decode=str.strip, alternative=None):
    return functools.cached_property(_attr_getter(filename, decode, alternative))


def attr(filename, decode=str.strip, alternative=None):
    return property(_attr_getter(filename, decode, alternative))


def _decode_speed(speed):
    match int(speed):
        case 1:
            return Speed.LOW
        case 12:
            return Speed.FULL
        case 480:
            return Speed.HIGH
        case 5000:
            return Speed.SUPER
        case 10000:
            return Speed.SUPER_PLUS
        case _:
            return Speed.UNKNOWN


def _manufacturer_alternative(device):
    from .usbids import V

    vendor_id = device.vendor_id
    return V.get(vendor_id, {}).get("name")


def _product_alternative(device):
    from .usbids import V

    vendor_id, product_id = device.vendor_id, device.product_id
    return V.get(vendor_id, {}).get("children", {}).get(product_id, {}).get("name")


def usb_video_control_descriptor(data, offset=0):
    vc = data[offset + 2]
    if vc == raw.VideoControl.HEADER:
        return raw.uvc_header_descriptor.from_buffer_copy(data, offset)
    elif vc == raw.VideoControl.INPUT_TERMINAL:
        return raw.uvc_input_terminal_descriptor.from_buffer_copy(data, offset)
    elif vc == raw.VideoControl.OUTPUT_TERMINAL:
        return raw.uvc_output_terminal_descriptor.from_buffer_copy(data, offset)
    elif vc == raw.VideoControl.EXTENSION_UNIT:
        return raw.uvc_extension_unit_descriptor.from_buffer_copy(data, offset)
    elif vc == raw.VideoControl.PROCESSING_UNIT:
        return raw.uvc_processing_unit_descriptor.from_buffer_copy(data, offset)
    elif vc == raw.VideoControl.SELECTOR_UNIT:
        return raw.uvc_selector_unit_descriptor.from_buffer_copy(data, offset)
    if offset:
        return data[offset:]
    return data


DESCRIPTOR_STRUCT_MAP = {
    DescriptorType.DEVICE: raw.usb_device_descriptor,
    DescriptorType.CONFIG: raw.usb_config_descriptor,
    DescriptorType.STRING: raw.usb_string_descriptor,
    DescriptorType.INTERFACE: raw.usb_interface_descriptor,
    DescriptorType.INTERFACE_ASSOCIATION: raw.usb_interface_assoc_descriptor,
    DescriptorType.ENDPOINT: raw.usb_endpoint_descriptor,
    DescriptorType.HID: raw.usb_hid_descriptor,
}

DESCRIPTOR_CALL_MAP = {
    DescriptorType.VIDEO_CONTROL: usb_video_control_descriptor,
}


class DeviceDescriptor:
    @classmethod
    def from_struct(cls, struct: raw.usb_device_descriptor):
        self = cls()
        self.usb_version = bcd_version(struct.bcdUSB)
        self.version = bcd_version(struct.bcdDevice)
        self.class_id = struct.bDeviceClass
        self.sub_class_id = struct.bDeviceSubClass
        self.vendor_id = struct.idVendor
        self.product_id = struct.idProduct
        self.nb_configurations = struct.bNumConfigurations
        return self


def _iter_decode_descriptors(data):
    offset, size = 0, len(data)
    while offset < size:
        length = data[offset]
        dtype = data[offset + 1]
        dclass = DESCRIPTOR_STRUCT_MAP.get(dtype)
        if dclass is None:
            dfunc = DESCRIPTOR_CALL_MAP.get(dtype)
            if dfunc is None:
                yield data[offset : offset + length]
            else:
                yield dfunc(data, offset)
        else:
            extra = sizeof(dclass) - length
            if extra:
                local = data[offset : offset + length] + extra * b"\x00"
                descriptor = dclass.from_buffer_copy(local)
            else:
                descriptor = dclass.from_buffer_copy(data, offset)
            yield descriptor
        offset += length


class Device(BaseDevice):
    bus_number = cached_attr("busnum", int)
    device_address = cached_attr("devnum", int)
    manufacturer = cached_attr("manufacturer", alternative=_manufacturer_alternative)
    product = cached_attr("product", alternative=_product_alternative)
    nb_interfaces = cached_attr("bNumInterfaces", int)
    nb_configurations = cached_attr("bNumConfigurations", int)
    speed = cached_attr("speed", _decode_speed)
    active_configuration = attr("bConfigurationValue", int)
    device_class_id = cached_attr("bDeviceClass", int)
    device_subclass_id = cached_attr("bDeviceSubClass", int)
    device_protocol_id = cached_attr("bDeviceProtocol", int)
    product_id = cached_attr("idProduct", lambda text: int(text, 16))
    vendor_id = cached_attr("idVendor", lambda text: int(text, 16))
    removable = cached_attr("removable", lambda text: Removable(text.strip()))

    def __init__(self, name_or_file, **kwargs):
        self.syspath = pathlib.Path(name_or_file)
        dev_name = USB_DEV_TMPFS_PATH / f"{self.bus_number:03d}" / f"{self.device_address:03d}"
        super().__init__(dev_name, **kwargs)

    def __repr__(self):
        return (
            f"{type(self).__name__}(bus={self.bus_number}, address={self.device_address}, syspath={self.syspath.stem})"
        )

    def _on_open(self):
        self._raw_descriptors = list(_iter_decode_descriptors(self._fobj.read()))


class Configuration:
    pass


class Interface:
    pass


def is_available():
    return sysfs.is_available()


def iter_paths():
    for path in sysfs.DEVICE_PATH.iterdir():
        name = path.name
        if (not name[0].isdigit() and not name.startswith("usb")) or ":" in name:
            continue
        yield path


def iter_devices():
    for path in iter_paths():
        yield Device(path)


find = make_find(iter_devices)


def lsusb():
    for dev in iter_devices():
        print(
            f"Bus {dev.bus_number:03d} Device {dev.device_address:03d}: ID {dev.vendor_id:04x}:{dev.product_id:04x} {dev.manufacturer} {dev.product} {dev.filename}"
        )


if __name__ == "__main__":
    lsusb()
