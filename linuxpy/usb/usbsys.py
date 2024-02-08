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
from .ids.klass import klass as classes

Speed = raw.UsbDeviceSpeed


class Removable(enum.Enum):
    UNKNOWN = "unknown"
    FIXED = "fixed"
    REMOVABLE = "removable"


def _attr_getter(filename, decode, alternative, mode="r"):
    def getter(self):
        path = self.syspath / filename
        if path.exists():
            with path.open(mode) as fobj:
                return decode(fobj.read())
        elif alternative:
            return alternative(self)

    return getter


def cached_attr(filename, decode=str.strip, alternative=None, mode="r"):
    return functools.cached_property(_attr_getter(filename, decode, alternative, mode))


def attr(filename, decode=str.strip, alternative=None, mode="r"):
    return property(_attr_getter(filename, decode, alternative, mode))


class Attr:
    def __get__(self, obj, klass=None):
        pass


def _decode_speed(speed):
    speed = int(speed)
    if speed == 1:
        return Speed.LOW
    elif speed == 12:
        return Speed.FULL
    elif speed == 480:
        return Speed.HIGH
    elif speed == 5_000:
        return Speed.SUPER
    elif speed == 10_000:
        return Speed.SUPER_PLUS
    return Speed.UNKNOWN


def _manufacturer_alternative(device):
    return get_vendor_name(device.vendor_id)


def _product_alternative(device):
    return get_product_name(device.vendor_id, device.product_id)


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


def descriptor_node(klass):
    klass._children = None
    klass._parent = None
    klass._device = None

    def get_parent(self):
        return self._parent

    def set_parent(self, parent):
        self._parent = parent

    def get_device(self):
        return self._device

    def set_device(self, device):
        self._device = device

    def get_children(self):
        if self._children is None:
            self._children = []
        return self._children

    def getitem(self, key):
        return self.children[key]

    def size(self):
        return len(self.children)

    def iterator(self):
        return iter(self.children)

    def get_type(self) -> DescriptorType:
        try:
            return DescriptorType(self.bDescriptorType)
        except ValueError:
            return self.bDescriptorType

    klass.parent = property(get_parent, set_parent)
    klass.device = property(get_device, set_device)
    klass.children = property(get_children)
    klass.type = property(get_type)
    klass.length = property(lambda self: self.bLength)
    klass.__getitem__ = getitem
    klass.__iter__ = iterator
    klass.__len__ = size
    return klass


def get_vendor(vendor_id: int) -> dict:
    from linuxpy.usb.ids.vendor import vendor

    return vendor.get(vendor_id, {})


def get_vendor_name(vendor_id: int) -> str:
    return get_vendor(vendor_id).get("name", "")


def get_products(vendor_id: int) -> dict:
    return get_vendor(vendor_id).get("children", {})


def get_product(vendor_id: int, product_id: int) -> dict:
    return get_products(vendor_id).get(product_id, {})


def get_product_name(vendor_id: int, product_id: int) -> str:
    return get_product(vendor_id, product_id).get("name", "")


def get_class(class_id: int) -> dict:
    return classes.get(class_id, {})


def get_class_name(class_id: int) -> str:
    return get_class(class_id).get("name", "")


def get_subclasses(class_id: int) -> dict:
    return get_class(class_id).get("children", {})


def get_subclass(class_id: int, subclass_id: int) -> dict:
    return get_subclasses(class_id).get(subclass_id, {})


def get_subclass_name(class_id: int, subclass_id: int) -> str:
    return get_subclass(class_id, subclass_id).get("name", "")


def get_protocols(class_id: int, subclass_id: int) -> dict:
    return get_subclass(class_id, subclass_id).get("children", {})


def get_protocol(class_id: int, subclass_id: int, protocol_id: int) -> dict:
    return get_protocols(class_id, subclass_id).get(protocol_id, {})


def get_protocol_name(class_id, subclass_id, protocol_id):
    return get_protocol(class_id, subclass_id, protocol_id).get("name", "")


@descriptor_node
class DeviceDescriptor(raw.usb_device_descriptor):
    @property
    def usb_version(self):
        return bcd_version(self.bcdUSB)

    @property
    def version(self):
        return bcd_version(self.bcdDevice)

    @property
    def class_id(self):
        return self.bDeviceClass

    @property
    def subclass_id(self):
        return self.bDeviceSubClass

    @property
    def protocol_id(self):
        return self.bDeviceProtocol

    @property
    def vendor_id(self):
        return self.idVendor

    @property
    def vendor_name(self):
        return get_vendor_name(self.vendor_id)

    @property
    def product_id(self):
        return self.idProduct

    @property
    def product_name(self):
        return get_product_name(self.vendor_id, self.product_id)

    @property
    def nb_configurations(self):
        return self.bNumConfigurations

    @property
    def device_class(self) -> raw.Class:
        return raw.Class(self.class_id)

    @property
    def class_name(self) -> str:
        return get_class_name(self.class_id)

    @property
    def subclass_name(self) -> str:
        return get_subclass_name(self.class_id, self.subclass_id)

    @property
    def protocol_name(self) -> str:
        return get_protocol_name(self.class_id, self.subclass_id, self.protocol_id)

    def __str__(self):
        return f"""\
type            {self.type.value:6} {self.type.name}
length          {self.length:6} bytes
class           {self.class_id:6} {self.class_name}
subclass        {self.subclass_id:6} {self.subclass_name}
protocol        {self.protocol_id:6} {self.protocol_name}
max packet size {self.bMaxPacketSize0:6}
version         {self.version:>6}
usb version     {self.usb_version:>6}
vendor          0x{self.vendor_id:4x} {self.vendor_name}
product         0x{self.product_id:4x} {self.product_name}
manufacturer    {self.iManufacturer:6}
product         {self.iProduct:6}
serial number   {self.iSerialNumber:6}
nb. configs     {self.nb_configurations:6}"""


@descriptor_node
class Configuration(raw.usb_config_descriptor):
    @property
    def max_power(self) -> int:
        """
        Maximum  power consumption in this specific configuration when the
        device is fully operational (mA).
        """
        return self.bMaxPower * 2

    @property
    def is_self_powered(self) -> bool:
        return bool(self.bmAttributes & 0b100000)

    @property
    def has_remote_wakeup(self) -> bool:
        return bool(self.bmAttributes & 0b10000)


@descriptor_node
class Interface(raw.usb_interface_descriptor):
    @property
    def class_id(self):
        return self.bInterfaceClass

    @property
    def subclass_id(self):
        return self.bInterfaceSubClass

    @property
    def protocol_id(self):
        return self.bInterfaceProtocol

    @property
    def interface_class(self) -> raw.Class:
        return raw.Class(self.class_id)

    @property
    def interface_subclass(self):
        if self.interface_class == raw.Class.VIDEO:
            return raw.VideoSubClass(self.subclass_id)
        return self.subclass_id

    @property
    def class_name(self) -> str:
        return get_class_name(self.class_id)

    @property
    def subclass_name(self) -> str:
        return get_subclass_name(self.class_id, self.subclass_id)

    @property
    def protocol_name(self) -> str:
        return get_protocol_name(self.class_id, self.subclass_id, self.protocol_id)


@descriptor_node
class Endpoint(raw.usb_endpoint_descriptor):
    DIRECTION_MASK = 0x80
    TRANSFER_TYPE_MASK = 0b11

    @property
    def address(self):
        return self.bEndpointAddress

    @property
    def direction(self):
        return raw.Direction(self.address & self.DIRECTION_MASK)

    @property
    def transfer_type(self):
        return raw.EndpointTransferType(self.bmAttributes & self.TRANSFER_TYPE_MASK)

    def read(self):
        return self.device.read()

    def __repr__(self):
        name = type(self).__name__
        return f"{name} address=0x{self.address:X} type={self.transfer_type.name} direction={self.direction.name}"


class HID(raw.usb_hid_descriptor):
    @property
    def version(self):
        return bcd_version(self.bcdHID)


DESCRIPTOR_HIERARCHY = {
    DescriptorType.DEVICE: None,
    DescriptorType.CONFIG: DescriptorType.DEVICE,
    DescriptorType.INTERFACE: DescriptorType.CONFIG,
    DescriptorType.ENDPOINT: DescriptorType.INTERFACE,
    DescriptorType.INTERFACE_ASSOCIATION: DescriptorType.CONFIG,
    DescriptorType.VIDEO_CONTROL: DescriptorType.INTERFACE,
    DescriptorType.HID: DescriptorType.INTERFACE,
}


DESCRIPTOR_STRUCT_MAP = {
    DescriptorType.DEVICE: DeviceDescriptor,
    DescriptorType.CONFIG: Configuration,
    DescriptorType.STRING: raw.usb_string_descriptor,
    DescriptorType.INTERFACE: Interface,
    DescriptorType.INTERFACE_ASSOCIATION: raw.usb_interface_assoc_descriptor,
    DescriptorType.ENDPOINT: Endpoint,
    DescriptorType.HID: HID,
}


DESCRIPTOR_CALL_MAP = {
    DescriptorType.VIDEO_CONTROL: usb_video_control_descriptor,
}


def descs(data):
    size = len(data)
    ptr = 0
    while ptr < (size - 2):
        length, dtype = data[ptr], data[ptr + 1]
        try:
            name = DescriptorType(dtype).name
        except ValueError:
            name = str(dtype)
        print(name, dtype, length)
        ptr += length


def _iter_decode_descriptors(data):
    offset, size = 0, len(data)
    while offset < size:
        length = data[offset]
        dtype = data[offset + 1]
        dclass = DESCRIPTOR_STRUCT_MAP.get(dtype)
        if dclass is None:
            dfunc = DESCRIPTOR_CALL_MAP.get(dtype)
            if dfunc is not None:
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


def iter_descriptors(data):
    last_type = {}
    for item in _iter_decode_descriptors(data):
        if isinstance(item, bytes):
            continue
        dtype = item.bDescriptorType
        last_type[dtype] = item
        parent_type = DESCRIPTOR_HIERARCHY[dtype]
        if parent_type is not None:
            parent = last_type[parent_type]
            parent.children.append(item)
            item.parent = parent
        yield item


def build_descriptor(data):
    return list(iter_descriptors(data))[0]


def find_descriptor(desc, find_all=False, custom_match=None, **args):
    def desc_iter(**kwargs):
        for d in desc:
            tests = (val == getattr(d, key) for key, val in kwargs.items())
            if all(tests) and (custom_match is None or custom_match(d)):
                yield d

    result = desc_iter(**args)
    return result if find_all else next(result, None)


class Device(BaseDevice):
    descriptors = cached_attr("descriptors", build_descriptor, mode="rb")
    bus_number = cached_attr("busnum", int)
    device_number = cached_attr("devnum", int)
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
        dev_name = USB_DEV_TMPFS_PATH / f"{self.bus_number:03d}" / f"{self.device_number:03d}"
        super().__init__(dev_name, **kwargs)

    def __repr__(self):
        return f"{type(self).__name__}(bus={self.bus_number}, device={self.device_number}, syspath={self.syspath.stem})"

    def _on_open(self):
        self.descriptor = build_descriptor(self._fobj.read())


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


find = make_find(iter_devices, needs_open=False)


def lsusb():
    for dev in iter_devices():
        print(
            f"Bus {dev.bus_number:03d} Device {dev.device_number:03d}: ID {dev.vendor_id:04x}:{dev.product_id:04x} {dev.manufacturer} {dev.product}"
        )


if __name__ == "__main__":
    lsusb()
