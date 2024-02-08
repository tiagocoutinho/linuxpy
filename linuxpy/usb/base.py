import array
import enum
import errno
import pathlib

from .. import device, ioctl, kernel
from ..ctypes import cast, cuint, cvoidp, pointer, u8, u32
from . import raw

USB_DEV_PATH = pathlib.Path("/dev")
USB_DEV_TMPFS_PATH = USB_DEV_PATH / "bus" / "usb"

DT_DEVICE_SIZE = 18
DT_CONFIG_SIZE = 9
DT_INTERFACE_SIZE = 9
DT_ENDPOINT_SIZE = 7
DT_ENDPOINT_AUDIO_SIZE = 9  # Audio extension
DT_HUB_NONVAR_SIZE = 7
DT_SS_ENDPOINT_COMPANION_SIZE = 6
DT_BOS_SIZE = 5
DT_DEVICE_CAPABILITY_SIZE = 3

if kernel.VERSION >= (5, 2, 0):
    MAX_ISO_PACKET = 98304
elif kernel.VERSION >= (3, 10, 0):
    MAX_ISO_PACKET = 49152
else:
    MAX_ISO_PACKET = 8192


class TransferType(enum.IntEnum):
    CONTROL = 0x0
    ISOCHRONOUS = 0x1
    BULK = 0x2
    INTERRUPT = 0x3


class DescriptorType(enum.IntEnum):
    DEVICE = 0x1
    CONFIG = 0x2
    STRING = 0x3
    INTERFACE = 0x4
    ENDPOINT = 0x5
    INTERFACE_ASSOCIATION = 0x0B
    BOS = 0x0F
    DEVICE_CAPABILITY = 0x10
    HID = 0x21
    REPORT = 0x22
    PHYSICAL = 0x23
    VIDEO_CONTROL = 0x24

    HUB = 0x29
    SUPERSPEED_HUB = 0x2A
    SS_ENDPOINT_COMPANION = 0x30


def set_configuration(fd, n):
    n = cuint(n)
    return ioctl.ioctl(fd, raw.IOC.SETCONFIGURATION, n)


def claim_interface(fd, n):
    n = cuint(n)
    return ioctl.ioctl(fd, raw.IOC.CLAIMINTERFACE, n)


def active_configuration(fd):
    result = u8(0)
    ctrl = raw.usbdevfs_ctrltransfer()
    ctrl.bRequestType = raw.Direction.IN
    ctrl.bRequest = raw.Request.GET_CONFIGURATION
    ctrl.wValue = 0
    ctrl.wIndex = 0
    ctrl.wLength = 1
    ctrl.timeout = 1000
    ctrl.data = cast(pointer(result), cvoidp)
    ioctl.ioctl(fd, raw.IOC.CONTROL, ctrl)
    return result.value


def get_kernel_driver(fd, interface):
    result = raw.usbdevfs_getdriver()
    result.interface = interface
    try:
        ioctl.ioctl(fd, raw.IOC.GETDRIVER, result)
    except OSError as error:
        if error.errno == errno.ENODATA:
            return
        raise
    return result.driver.decode()


def connect(fd, interface):
    command = raw.usbdevfs_ioctl()
    command.ifno = interface
    command.ioctl_code = raw.IOC.CONNECT
    ioctl.ioctl(fd, raw.IOC.IOCTL, command)


def disconnect(fd, interface):
    command = raw.usbdevfs_ioctl()
    command.ifno = interface
    command.ioctl_code = raw.IOC.DISCONNECT
    try:
        ioctl.ioctl(fd, raw.IOC.IOCTL, command)
    except OSError as error:
        if error.errno == errno.ENODATA:
            return False
        raise
    return True


def capabilities(fd):
    caps = u32()
    ioctl.ioctl(fd, raw.IOC.GET_CAPABILITIES, caps)
    return raw.Capability(caps.value)


def speed(fd):
    result = ioctl.ioctl(fd, raw.IOC.GET_SPEED)
    return raw.UsbDeviceSpeed(result)


def bulk_read(fd, endpoint_address: int):
    data = array.array("B", 4096 * b"\x00")
    addr, length = data.buffer_info()
    nbytes = length * data.itemsize

    urb = raw.usbdevfs_urb()
    urb.usercontext = 0
    urb.type = raw.URBType.BULK
    urb.stream_id = 0
    urb.endpoint = endpoint_address
    urb.buffer = addr
    urb.buffer_length = nbytes
    ioctl.ioctl(fd, raw.IOC.SUBMITURB, urb)

    import select

    r, _, e = select.select((fd,), (), (fd,))
    reply = raw.usbdevfs_urb()
    return ioctl.ioctl(fd, raw.IOC.REAPURBNDELAY, reply)


class BaseDevice(device.BaseDevice):
    def __repr__(self):
        return f"{type(self).__name__}(bus={self.bus_number}, address={self.device_address})"

    @property
    def bus_number(self):
        raise NotImplementedError

    @property
    def device_address(self):
        raise NotImplementedError

    @property
    def session_id(self):
        return (self.bus_number << 8) | self.device_address

    @property
    def active_configuration(self):
        return active_configuration(self.fileno())

    @property
    def capabilities(self):
        return capabilities(self.fileno())

    @property
    def speed(self):
        return speed(self.fileno())

    def get_kernel_driver(self, interface):
        return get_kernel_driver(self.fileno(), interface)

    def connect(self, interface):
        connect(self.fileno(), interface)

    def disconnect(self, interface):
        disconnect(self.fileno(), interface)

    def set_configuration(self, n):
        return set_configuration(self.fileno(), n)

    def claim_interface(self, n):
        return claim_interface(self.fileno(), n)

    def bulk_read(self, endpoint):
        return bulk_read(self.fileno(), endpoint.address)
