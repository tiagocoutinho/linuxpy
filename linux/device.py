import os
import pathlib


PathType = pathlib.Path | str


class ReentrantContextManager:
    def __init__(self):
        self._context_level = 0

    def __enter__(self):
        if not self._context_level:
            self.open()
        self._context_level += 1
        return self

    def __exit__(self, *exc):
        self._context_level -= 1
        if not self._context_level:
            self.close()

    def open(self):
        raise NotImplementedError
    
    def close(self):
        raise NotImplementedError


def device_number(path: PathType):
    """Retrieves device """
    num = ""
    for c in str(path)[::-1]:
        if c.isdigit():
            num = c + num
        else:
            break
    return int(num) if num else None


def is_device_file(path: PathType, read_write: bool = True):
    """Check if path is a readable (and, optionally, writable) character device."""
    path = pathlib.Path(path)
    if not path.is_char_device():
        return False
    access = os.R_OK | (os.W_OK if read_write else 0)
    if not os.access(str(path), access):
        return False
    return True


def iter_device_files(path: PathType = "/dev", pattern: str = "*") -> list[pathlib.Path]:
    path = pathlib.Path(path)
    items = path.glob(pattern)

    return filter(is_device_file, items)
