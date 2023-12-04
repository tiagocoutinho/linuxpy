#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import asyncio
import collections
import enum
import functools
import os
import pathlib
import select
from typing import Union

from linuxpy.ctypes import cast, cint, create_string_buffer, cuint, cvoidp, i32, sizeof
from linuxpy.device import BaseDevice, iter_device_files
from linuxpy.ioctl import IO as _IO, IOR as _IOR, IOW as _IOW, IOWR as _IOWR, ioctl
from linuxpy.util import add_reader_asyncio, make_find

from .raw import (
    UIOC,
    Absolute,
    AutoRepeat,
    Bus,
    EventType,
    ForceFeedback,
    Key,
    Led,
    Miscelaneous,
    Relative,
    Sound,
    Switch,
    Synchronization,
    ff_effect,
    input_absinfo,
    input_event,
    input_id,
    input_mask,
    uinput_setup,
)

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


def read_name(fd):
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
    return {event_type: event_type_capabilities(fd, event_type) for event_type in event_types}


def capabilities_str(caps, indent=""):
    lines = []
    sub_indent = indent if indent else "  "
    for cap, values in caps.items():
        lines.append(f"{indent}{ cap.name}:")
        lines.extend(2 * sub_indent + value.name for value in values)
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
        fields = {name: funcs.get(name, _identity)(s, getattr(s, name)) for name in field_names}
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


class InputError(Exception):
    pass


class _Type:
    _event_type = None

    def __init__(self, device=None):
        self.device = device

    def __get__(self, obj, type=None):
        if self._event_type not in obj.capabilities:
            name = EVENT_TYPE_MAP[self._event_type].__name__.lower()
            raise ValueError(f"device has no {name!r} capability")
        return self.__class__(obj)

    def _check_code(self, code):
        if code not in self.device.capabilities[self._event_type]:
            raise ValueError(f"device has no {code.name!r} capability")


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
    PREFIX = "/dev/input/event"

    absolute = _Abs()
    keys = _Keys()

    def __init__(self, *args, **kwargs):
        self._caps = None
        super().__init__(*args, **kwargs)

    def __iter__(self):
        with EventReader(self) as reader:
            while True:
                yield reader.read()

    async def __aiter__(self):
        async with EventReader(self) as reader:
            while True:
                yield await reader.aread()

    def _on_open(self):
        pass

    @functools.cached_property
    def uid(self):
        return uid(self.fileno())

    @functools.cached_property
    def name(self):
        return read_name(self.fileno())

    @functools.cached_property
    def version(self):
        return version(self.fileno())

    @functools.cached_property
    def physical_location(self):
        return physical_location(self.fileno())

    @functools.cached_property
    def device_id(self):
        return device_id(self.fileno())

    @functools.cached_property
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


class EventReader:
    def __init__(self, device: Device, max_queue_size=1):
        self.device = device
        self._loop = None
        self._selector = None
        self._buffer = None
        self._max_queue_size = max_queue_size

    async def __aenter__(self):
        if self.device.is_blocking:
            raise InputError("Cannot use async event reader on blocking device")
        self._buffer = asyncio.Queue(maxsize=self._max_queue_size)
        self._selector = select.epoll()
        self._loop = asyncio.get_event_loop()
        self._loop.add_reader(self._selector.fileno(), self._on_event)
        self._selector.register(self.device.fileno(), select.POLLIN)
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        self._selector.unregister(self.device.fileno())
        self._loop.remove_reader(self._selector.fileno())
        self._selector.close()
        self._selector = None
        self._loop = None
        self._buffer = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        pass

    def _on_event(self):
        task = self._loop.create_future()
        try:
            self._selector.poll(0)  # avoid blocking
            data = self.device.read_event()
            task.set_result(data)
        except Exception as error:
            task.set_exception(error)

        buffer = self._buffer
        if buffer.full():
            self.device.log.warn("missed event")
            buffer.get_nowait()
        buffer.put_nowait(task)

    def read(self, timeout=None):
        if not self.device.is_blocking:
            read, _, _ = self.device.io.select((self.device,), (), (), timeout)
            if not read:
                return
        return self.device.read_event()

    async def aread(self):
        """Wait for next event or return last event"""
        task = await self._buffer.get()
        return await task


def event_stream(fd):
    while True:
        select.select((fd,), (), ())
        yield InputEvent.from_struct(read_event(fd))


async def async_event_stream(fd, maxsize=1000):
    queue = asyncio.Queue(maxsize=maxsize)
    with add_reader_asyncio(fd, lambda: queue.put_nowait(read_event(fd))):
        while True:
            yield InputEvent.from_struct(await queue.get())


def event_batch_stream(fd):
    """Yields packets of events occurring at the same moment in time."""
    packet = []
    for event in event_stream(fd):
        if event.type == EventType.SYN:
            if event.code == Synchronization.REPORT:
                yield packet
                packet = []
            elif event.code == Synchronization.DROPPED:
                packet = []
        else:
            packet.append(event)


async def async_event_batch_stream(fd, maxsize=1000):
    """Yields packets of events occurring at the same moment in time."""
    packet = []
    async for event in async_event_stream(fd, maxsize=maxsize):
        if event.type == EventType.SYN:
            if event.code == Synchronization.REPORT:
                yield packet
                packet = []
            elif event.code == Synchronization.DROPPED:
                packet = []
        else:
            packet.append(event)


def iter_devices(path="/dev/input", **kwargs):
    return (Device(path, **kwargs) for path in iter_input_files(path=path))


find = make_find(iter_devices)


def is_gamepad(device: Device) -> bool:
    with device:
        caps = device.capabilities
    key_caps = caps.get(EventType.KEY, ())
    return EventType.ABS in caps and Key.BTN_GAMEPAD in key_caps


def is_keyboard(device: Device) -> bool:
    with device:
        caps = device.capabilities
    key_caps = caps.get(EventType.KEY, ())
    return Key.KEY_A in key_caps and Key.KEY_CAPSLOCK in key_caps


def is_mouse(device: Device) -> bool:
    with device:
        caps = device.capabilities
    if EventType.ABS not in caps and EventType.REL not in caps:
        return False
    key_caps = caps.get(EventType.KEY, ())
    return Key.BTN_MOUSE in key_caps


def _filter_devices(func):
    return filter(func, iter_devices())


def find_gamepads():
    return _filter_devices(is_gamepad)


def find_keyboards():
    return _filter_devices(is_keyboard)


def find_mice():
    return _filter_devices(is_mouse)


def is_uinput_available():
    return BaseUDevice.PATH.exists()


def u_device_setup(fd, bus: Bus, vendor: int, product: int, name: Union[str, bytes]) -> None:
    setup = uinput_setup()
    setup.id.bustype = bus
    setup.id.vendor = vendor
    setup.id.product = product
    name = name[:80]
    if isinstance(name, str):
        name = name.encode()
    setup.name = name
    ioctl(fd, UIOC.DEV_SETUP, setup)


def u_device_create(fd):
    ioctl(fd, UIOC.DEV_CREATE)


def u_device_destroy(fd):
    ioctl(fd, UIOC.DEV_DESTROY)


def u_set_event(fd, event_type: EventType):
    ioctl(fd, UIOC.SET_EVBIT, event_type)


def _u_set_n(fd, ioc, values):
    for value in values:
        ioctl(fd, ioc, value)


def u_set_keys(fd, *keys: Key):
    _u_set_n(fd, UIOC.SET_KEYBIT, keys)


def u_set_relatives(fd, *relatives: Relative):
    _u_set_n(fd, UIOC.SET_RELBIT, relatives)


def u_set_absolutes(fd, *absolutes: Absolute):
    _u_set_n(fd, UIOC.SET_ABSBIT, absolutes)


def u_set_miscellaneous(fd, *misc: Miscelaneous):
    _u_set_n(fd, UIOC.SET_MSCBIT, misc)


def u_set_force_feedback(fd, *ff: ForceFeedback):
    _u_set_n(fd, UIOC.SET_FFBIT, ff)


def u_emit(fd, event_type, event_code, value, syn=True):
    event = input_event()
    event.type = event_type
    event.code = event_code
    event.value = value
    os.write(fd, bytes(event))
    if syn:
        u_emit(fd, EventType.SYN, Synchronization.REPORT, Synchronization.REPORT, syn=False)


class BaseUDevice(BaseDevice):
    """A uinput device with no capabilities registered"""

    PATH = pathlib.Path("/dev/uinput")
    CAPABILITIES = {}

    def __init__(
        self,
        filename=PATH,
        bus=Bus.USB,
        vendor_id=0x01,
        product_id=0x01,
        name="linuxpy emulated device",
    ):
        # Force write only
        super().__init__(filename, read_write="w")
        self.bustype = bus
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.name = name

    def _on_open(self):
        self.setup()
        self.create()

    def _on_close(self):
        self.destroy()

    def setup(self):
        self.set_capabilities(self.CAPABILITIES)
        u_device_setup(self.fileno(), self.bustype, self.vendor_id, self.product_id, self.name)

    def set_capabilities(self, caps: dict):
        for event_type, capabilities in caps.items():
            u_set_event(self.fileno(), event_type)
            if event_type == EventType.KEY:
                u_set_keys(self.fileno(), *capabilities)
            elif event_type == EventType.ABS:
                u_set_absolutes(self.fileno(), *capabilities)
            elif event_type == EventType.REL:
                u_set_relatives(self.fileno(), *capabilities)
            elif event_type == EventType.MSC:
                u_set_miscellaneous(self.fileno(), *capabilities)
            elif event_type == EventType.FF:
                u_set_force_feedback(self.fileno(), *capabilities)

    def create(self):
        u_device_create(self.fileno())

    def destroy(self):
        u_device_destroy(self.fileno())

    def emit(self, event_type: EventType, event_code: int, value: int, syn=True):
        return u_emit(self.fileno(), event_type, event_code, value, syn=syn)


class UMouse(BaseUDevice):
    CAPABILITIES = {
        EventType.KEY: {Key.BTN_LEFT, Key.BTN_MIDDLE, Key.BTN_RIGHT},
        EventType.REL: {Relative.X, Relative.Y},
    }


class UGamepad(BaseUDevice):
    CAPABILITIES = {
        #        EventType.FF: {ForceFeedback.RUMBLE, ForceFeedback.PERIODIC, ForceFeedback.SQUARE, ForceFeedback.TRIANGLE, ForceFeedback.SINE, ForceFeedback.GAIN},
        EventType.KEY: {
            Key.BTN_GAMEPAD,
            Key.BTN_EAST,
            Key.BTN_NORTH,
            Key.BTN_WEST,
            Key.BTN_EAST,
            Key.BTN_SELECT,
            Key.BTN_START,
            Key.BTN_TL,
            Key.BTN_TR,
            Key.BTN_TL2,
            Key.BTN_TR2,
            Key.BTN_MODE,
            Key.BTN_THUMBL,
            Key.BTN_THUMBR,
            Key.BTN_DPAD_UP,
            Key.BTN_DPAD_DOWN,
            Key.BTN_DPAD_LEFT,
            Key.BTN_DPAD_RIGHT,
        },
        EventType.ABS: {Absolute.X, Absolute.Y, Absolute.RX, Absolute.RY, Absolute.RZ},
        EventType.MSC: {Miscelaneous.SCAN},
    }
