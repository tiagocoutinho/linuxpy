from . import usbfs, usbsys


def iter_devices():
    # we can retrieve device list and descriptors from sysfs or usbfs.
    # sysfs is preferable, because if we use usbfs we end up resuming
    # any autosuspended USB devices. however, sysfs is not available
    # everywhere, so we need a usbfs fallback too.
    func = usbsys.iter_devices if usbsys.is_available else usbfs.iter_devices
    yield from func()
