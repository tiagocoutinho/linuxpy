import pathlib

from .magic import Magic
from .statfs import get_fs_type

MAGIC = Magic.SYSFS

MOUNT_PATH = pathlib.Path("/sys")
DEVICE_PATH = MOUNT_PATH / "bus/usb/devices"


def is_sysfs(path) -> bool:
    return get_fs_type(path) == MAGIC


def is_available() -> bool:
    return is_sysfs(MOUNT_PATH)
