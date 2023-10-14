import enum
import functools
import pathlib

from .. import sysfs
from .raw import UsbDeviceSpeed
from .base import BaseDevice, USB_DEV_TMPFS_PATH


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
        case 1: return UsbDeviceSpeed.LOW
        case 12: return UsbDeviceSpeed.FULL
        case 480: return UsbDeviceSpeed.HIGH
        case 5000: return UsbDeviceSpeed.SUPER
        case 10000: return UsbDeviceSpeed.SUPER_PLUS
        case _: return UsbDeviceSpeed.UNKNOWN


def _manufacturer_alternative(device):
    from .usbids import V
    vendor_id = device.vendor_id
    return V.get(vendor_id, {}).get("name")


def _product_alternative(device):
    from .usbids import V
    vendor_id, product_id = device.vendor_id, device.product_id
    return V.get(vendor_id, {}).get("children", {}).get(product_id, {}).get("name")


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
        return f"{type(self).__name__}(bus={self.bus_number}, address={self.device_address}, syspath={self.syspath.stem})"

    def _on_open(self):
        pass

def is_available():
    return sysfs.is_available()


def iter_paths():
    for path in sysfs.DEVICE_PATH.iterdir():
        name = path.name
        if (not name[0].isdigit() and not name.startswith('usb')) or ':' in name:
            continue
        yield path


def iter_devices():
    for path in iter_paths():
        yield Device(path)


def lsusb():
    for dev in iter_devices():
        print(f"Bus {dev.bus_number:03d} Device {dev.device_address:03d}: ID {dev.vendor_id:04x}:{dev.product_id:04x} {dev.manufacturer} {dev.product}")


if __name__ == "__main__":
    lsusb()