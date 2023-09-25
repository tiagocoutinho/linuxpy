#
# This file is part of the python-linux project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import asyncio
import collections
import enum
import functools
import select
import os

from linux.ctypes import cint, cuint, i32, cvoidp, sizeof, create_string_buffer, cast
from linux.device import iter_device_files, BaseDevice
from linux.ioctl import ioctl, IO as _IO, IOR as _IOR, IOW as _IOW, IOWR as _IOWR
from .raw import Bus, Key, Led, Sound, Switch, Synchronization, Relative, Absolute, Miscelaneous, AutoRepeat, ForceFeedback
from .raw import EventType
from .raw import input_id, input_absinfo, input_mask, input_event
from .raw import ff_effect


EVENT_SIZE = sizeof(input_event)

EVDEV_MAGIC = ord(b"E")

IO = functools.partial(_IO, EVDEV_MAGIC)
IOR = functools.partial(_IOR, EVDEV_MAGIC)
IOW = functools.partial(_IOW, EVDEV_MAGIC)
IOWR = functools.partial(_IOWR, EVDEV_MAGIC)


_S_BUFF = 512

def _enum_max(enu):
    # danger: assuming last enum element is _MAX (ex: Key is KEY_MAX)
    if isinstance(enu, enum.Enum):
        enu = type(enu)
    return tuple(enu)[-1]


def _enum_bit_size(enu):
    return _enum_max(enu) // 8 + 1


EVIOCGVERSION = IOR(0x01, cint)
EVIOCGID = IOR(0x02, input_id)
EVIOCGREP = IOR(0x03, 2 * cuint)
EVIOCGNAME = IOR(0x06, _S_BUFF)
EVIOCGPHYS = IOR(0x07, _S_BUFF)
EVIOCGUNIQ = IOR(0x08, _S_BUFF)
# EVIOCGPROP = _IOR(EVDEV_MAGIC, 0x09, _S_BUFF)
EVIOCGKEY = IOR(0x18, _enum_bit_size(Key))
EVIOCGLED = IOR(0x19, _enum_bit_size(Led))
EVIOCGSND = IOR(0x1A, _enum_bit_size(Sound))
EVIOCGSW = IOR(0x1B, _enum_bit_size(Switch))


def EVIOCGMTSLOTS(nb_slots):
    return IOR(0x0A, (nb_slots + 1) * sizeof(i32))


def EVIOCGBIT(event_type_value, size):
    return IOR(0x20 + event_type_value, size)


def EVIOCGABS(abs_type_value):
    return IOR(0x40 + abs_type_value, sizeof(input_absinfo))


def EVIOCSABS(abs_type_value):
    raise NotImplementedError


EVIOCSFF = IOW(0x80, ff_effect)
EVIOCRMFF = IOW(0x81, cint)
EVIOCGEFFECTS = IOR(0x84, cint)
EVIOCGRAB = IOW(0x90, cint)
EVIOCGMASK = IOR(0x92, input_mask)
EVIOCSMASK = IOW(0x93, input_mask)


EVENT_TYPE_MAP = {
    EventType.SYN: Synchronization,
    EventType.KEY: Key,
    EventType.REL: Relative,
    EventType.ABS: Absolute,
    EventType.MSC: Miscelaneous,
    EventType.SW: Switch,
    EventType.LED: Led,
    EventType.SND: Sound,
    EventType.REP: AutoRepeat,
    EventType.FF: ForceFeedback,
}


def grab(fd):
    ioctl(fd, EVIOCGRAB, 1)


def release(fd):
    ioctl(fd, EVIOCGRAB, 0)


def version(fd):
    result = cint()
    ioctl(fd, EVIOCGVERSION, result)
    return result.value


def device_id(fd):
    result = input_id()
    ioctl(fd, EVIOCGID, result)
    return result


def name(fd):
    result = create_string_buffer(_S_BUFF)
    ioctl(fd, EVIOCGNAME, result)
    return result.value.decode()


def physical_location(fd):
    result = create_string_buffer(_S_BUFF)
    ioctl(fd, EVIOCGPHYS, result)
    return result.value.decode()


def uid(fd):
    result = create_string_buffer(_S_BUFF)
    ioctl(fd, EVIOCGUNIQ, result)
    return result.value.decode()


def _bit(array, bit):
    return ord(array[bit // 8]) & (1 << (bit % 8))


def _active(fd, code, dtype):
    result = create_string_buffer(_enum_bit_size(dtype))
    ioctl(fd, code, result)
    return {item for item in dtype if _bit(result, item)}


def active_keys(fd):
    return _active(fd, EVIOCGKEY, Key)


def active_leds(fd):
    return _active(fd, EVIOCGLED, Led)


def active_sounds(fd):
    return _active(fd, EVIOCGSND, Sound)


def active_switches(fd):
    return _active(fd, EVIOCGSW, Switch)


def abs_info(fd, abs_code):
    result = input_absinfo()
    ioctl(fd, EVIOCGABS(abs_code), result)
    return result


def available_event_types(fd):
    nb_bytes = _enum_bit_size(EventType)
    result = create_string_buffer(nb_bytes)
    ioctl(fd, EVIOCGBIT(0, nb_bytes), result)
    return {ev_type for ev_type in EventType if _bit(result, ev_type)}


def event_type_capabilities(fd, event_type):
    if event_type == EventType.SYN:
        # cannot query EventType.SYN so just return all possibilities
        return list(Synchronization)[:-1]  # remove SYN_MAX
    elif event_type == EventType.REP:
        # nothing in particular to report
        return []
    event_code_type = EVENT_TYPE_MAP[event_type]
    nb_bytes = _enum_bit_size(event_code_type)
    event_codes_bits = create_string_buffer(nb_bytes)
    ioctl(fd, EVIOCGBIT(event_type, nb_bytes), event_codes_bits)
    return {c for c in event_code_type if _bit(event_codes_bits, c)}


def auto_repeat_settings(fd):
    result = (cuint * 2)()
    ioctl(fd, EVIOCGREP, result)
    return {rep: result[rep] for rep in AutoRepeat}


def capabilities(fd):
    event_types = available_event_types(fd)
    return {
        event_type: event_type_capabilities(fd, event_type)
        for event_type in event_types
    }


def capabilities_str(caps, indent=""):
    lines = []
    sub_indent = indent if indent else "  "
    for cap, values in caps.items():
        lines.append("{}{}:".format(indent, cap.name))
        lines.extend((2 * sub_indent + value.name for value in values))
    return "\n".join(lines)


def get_input_mask(fd, event_type):
    event_code_type = EVENT_TYPE_MAP[event_type]
    nb_bytes = _enum_bit_size(event_code_type)
    event_codes_bits = create_string_buffer(nb_bytes)
    result = input_mask()
    result.type = event_type
    result.codes_size = nb_bytes
    result.codes_ptr = cast(event_codes_bits, cvoidp)
    ioctl(fd, EVIOCGMASK, result)
    return result, event_codes_bits


def read_event(fd, read=os.read):
    data = read(fd, EVENT_SIZE)
    if len(data) < EVENT_SIZE:
        raise ValueError
    return input_event.from_buffer_copy(data)


def iter_input_files(path="/dev/input", pattern="event*"):
    """List readable character devices in the given path."""
    return iter_device_files(path, pattern)


def _build_struct_type(struct, funcs=None):
    name = "".join(map(str.capitalize, struct.__name__.split("_")))
    field_names = [f[0] for f in struct._fields_]
    klass = collections.namedtuple(name, field_names)
    if funcs is None:
        funcs = {}

    def _identity(o, v):
        return v

    def from_struct(s):
        fields = {
            name: funcs.get(name, _identity)(s, getattr(s, name))
            for name in field_names
        }
        return klass(**fields)

    klass.from_struct = from_struct
    return klass


InputId = _build_struct_type(input_id, {"bustype": lambda o, v: Bus(v)})
InputEvent = _build_struct_type(
    input_event,
    {
        "time": lambda o, t: t.secs + (t.usecs) * 1e-6,
        "type": lambda o, t: EventType(t),
        "code": lambda o, c: EVENT_TYPE_MAP[o.type](c),
    },
)


class _Type:
    _event_type = None

    def __init__(self, device=None):
        self.device = device

    def __get__(self, obj, type=None):
        if self._event_type not in obj.capabilities:
            name = EVENT_TYPE_MAP[self._event_type].__name__.lower()
            raise ValueError("device has no {!r} capability".format(name))
        return self.__class__(obj)

    def _check_code(self, code):
        if code not in self.device.capabilities[self._event_type]:
            raise ValueError("device has no {!r} capability".format(code.name))


class _Abs(_Type):
    _event_type = EventType.ABS

    def __getitem__(self, code):
        self._check_code(code)
        return self.device.get_abs_info(code).value

    def __getattr__(self, key):
        name = "ABS_" + key.upper()
        try:
            return self[Absolute[name]]
        except KeyError:
            return super().__getattr__(key)

    def __dir__(self):
        return [k.name[4:].lower() for k in self.device.capabilities[self._event_type]]


class _Keys(_Type):
    _event_type = EventType.KEY

    def __dir__(self):
        return [k.name for k in self.device.capabilities[self._event_type]]

    def __getitem__(self, code):
        self._check_code(code)
        return code in self.device.active_keys

    def __getattr__(self, name):
        try:
            return self[Key[name.upper()]]
        except KeyError:
            return super().__getattr__(name)


class Device(BaseDevice):
    absolute = _Abs()
    keys = _Keys()

    def __init__(self, *args, **kwargs):
        self._caps = None
        super().__init__(*args, **kwargs)

    def _init(self):
        pass

    @property
    def uid(self):
        return uid(self.fileno())

    @property
    def name(self):
        return name(self.fileno())

    @property
    def version(self):
        return version(self.fileno())

    @property
    def physical_location(self):
        return physical_location(self.fileno())

    @property
    def device_id(self):
        return device_id(self.fileno())

    @property
    def capabilities(self):
        if self._caps is None:
            self._caps = capabilities(self.fileno())
        return self._caps

    @property
    def active_keys(self):
        return active_keys(self.fileno())

    def get_abs_info(self, abs_code):
        return abs_info(self.fileno(), abs_code)

    @property
    def x(self):
        return self.get_abs_info(Absolute.X).value

    @property
    def y(self):
        return self.get_abs_info(Absolute.Y).value

    @property
    def z(self):
        return self.get_abs_info(Absolute.Z).value

    @property
    def rx(self):
        return self.get_abs_info(Absolute.RX).value

    @property
    def ry(self):
        return self.get_abs_info(Absolute.RY).value

    @property
    def rz(self):
        return self.get_abs_info(Absolute.RZ).value

    def read_event(self):
        """
        Read event.
        Event must be available to read or otherwise will raise an error
        """
        return InputEvent.from_struct(read_event(self.fileno()))


def event_stream(fd):
    while True:
        select.select((fd,), (), ())
        yield InputEvent.from_struct(read_event(fd))


async def async_event_stream(fd, maxsize=1000):
    loop = asyncio.get_event_loop()
    queue = asyncio.Queue(maxsize=maxsize)
    loop.add_reader(fd, lambda: queue.put_nowait(read_event(fd)))
    try:
        while True:
            yield InputEvent.from_struct(await queue.get())
    finally:
        loop.remove_reader(fd)


def find_gamepads():
    for path in iter_input_files():
        with Device(path) as dev:
            caps = dev.capabilities
        if EventType.ABS in caps and Key.BTN_GAMEPAD in caps.get(
            EventType.KEY, ()
        ):
            yield dev


def find_keyboards():
    for path in iter_input_files():
        with Device(path) as dev:
            caps = dev.capabilities
        key_caps = caps.get(EventType.KEY, ())
        if Key.KEY_A in key_caps and Key.KEY_CAPSLOCK in key_caps:
            yield dev


def main():
    import sys

    with Device(sys.argv[1]) as dev:
        print("version:", version(dev))
        print(
            "ID: bus={0.bustype} vendor={0.vendor} product={0.product} "
            "version={0.version}".format(device_id(dev))
        )
        print("name:", name(dev))
        print("physical_location:", physical_location(dev))
        #    print('UID:', uid(fd))
        print(
            "capabilities:\n{}".format(capabilities_str(capabilities(dev), indent="  "))
        )
        print("key state:", active_keys(dev))

    return dev


if __name__ == "__main__":
    dev = main()

