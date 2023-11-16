#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import asyncio
import select

from linuxpy import ctypes
from linuxpy.ctypes import Struct, cint, sizeof
from linuxpy.device import DEV_PATH, BaseDevice
from linuxpy.ioctl import ioctl
from linuxpy.midi.raw import (
    IOC,
    EventLength,
    EventType,
    PortCapability,
    PortType,
    TimeMode,
    TimeStamp,
    snd_seq_addr,
    snd_seq_client_info,
    snd_seq_event,
    snd_seq_port_info,
    snd_seq_port_subscribe,
    snd_seq_running_info,
    snd_seq_system_info,
)
from linuxpy.types import Iterable, Optional, Sequence, Union
from linuxpy.util import add_reader_asyncio

ALSA_PATH = DEV_PATH / "snd"
SEQUENCER_PATH = ALSA_PATH / "seq"

SYSEX_START = 0xF0
SYSEX_END = 0xF7

EVENT_SIZE = sizeof(snd_seq_event)

READ = PortCapability.READ | PortCapability.SUBS_READ
WRITE = PortCapability.WRITE | PortCapability.SUBS_WRITE
READ_WRITE = READ | WRITE


class MidiError(Exception):
    pass


def read_pversion(seq) -> int:
    pversion = cint()
    ioctl(seq, IOC.PVERSION, pversion)
    return pversion.value


def read_system_info(seq) -> snd_seq_system_info:
    info = snd_seq_system_info()
    ioctl(seq, IOC.SYSTEM_INFO, info)
    return info


def read_running_mode(seq) -> snd_seq_running_info:
    info = snd_seq_running_info()
    ioctl(seq, IOC.RUNNING_MODE, info)
    return info


def read_client_id(seq) -> int:
    client_id = cint()
    ioctl(seq, IOC.CLIENT_ID, client_id)
    return client_id.value


def read_client_info(seq, client_id: int) -> snd_seq_client_info:
    client = snd_seq_client_info(client=client_id)
    ioctl(seq, IOC.GET_CLIENT_INFO, client)
    return client


def write_client_info(seq, client: snd_seq_client_info):
    ioctl(seq, IOC.SET_CLIENT_INFO, client)
    return client


def next_client(seq, client_id: int) -> Optional[snd_seq_client_info]:
    client = snd_seq_client_info(client=client_id)
    try:
        ioctl(seq, IOC.QUERY_NEXT_CLIENT, client)
    except FileNotFoundError:
        return None
    return client


def iter_read_clients(seq) -> Iterable[snd_seq_client_info]:
    next_client_id = -1
    while client := next_client(seq, next_client_id):
        yield client
        next_client_id = client.client


def read_port_info(seq, client_id: int, port_id: int) -> snd_seq_port_info:
    port = snd_seq_port_info(client=client_id)
    port.addr.client = client_id
    port.addr.port = port_id
    ioctl(seq, IOC.GET_PORT_INFO, port)
    return port


def next_port(seq, client_id: int, port_id: int) -> Optional[snd_seq_port_info]:
    port = snd_seq_port_info(client=client_id)
    port.addr.client = client_id
    port.addr.port = port_id
    try:
        ioctl(seq, IOC.QUERY_NEXT_PORT, port)
    except FileNotFoundError:
        return None
    return port


def iter_read_ports(seq, client_id: int) -> Iterable[snd_seq_port_info]:
    next_port_id = -1
    while port := next_port(seq, client_id, next_port_id):
        yield port
        next_port_id = port.addr.port


def create_port(seq, port: snd_seq_port_info):
    ioctl(seq, IOC.CREATE_PORT, port)


def delete_port(seq, port: snd_seq_port_info):
    ioctl(seq, IOC.DELETE_PORT, port)


def subscribe(seq, src_client_id: int, src_port_id: int, dest_client_id: int, dest_port_id: int):
    subs = snd_seq_port_subscribe()
    subs.sender.client = src_client_id
    subs.sender.port = src_port_id
    subs.dest.client = dest_client_id
    subs.dest.port = dest_port_id
    ioctl(seq, IOC.SUBSCRIBE_PORT, subs)


def unsubscribe(seq, src_client_id: int, src_port_id: int, dest_client_id: int, dest_port_id: int):
    subs = snd_seq_port_subscribe()
    subs.sender.client = src_client_id
    subs.sender.port = src_port_id
    subs.dest.client = dest_client_id
    subs.dest.port = dest_port_id
    ioctl(seq, IOC.UNSUBSCRIBE_PORT, subs)


class Version:
    def __init__(self, major: int, minor: int, patch: int):
        self.major = major
        self.minor = minor
        self.patch = patch

    @classmethod
    def from_tuple(cls, sequence: Iterable[str | int]):
        return cls(*map(int, sequence))

    @classmethod
    def from_str(cls, text):
        return cls.from_tuple(text.split(".", 2))

    @classmethod
    def from_number(cls, number: int):
        return cls((number >> 16) & 0xFF, (number >> 8) & 0xFF, number & 0xFF)

    def __int__(self):
        return (self.major << 16) + (self.minor << 8) + self.patch

    def __repr__(self):
        return f"{self.major}.{self.minor}.{self.patch}"

    def __getitem__(self, item):
        return self.tuple[item]

    def __eq__(self, other):
        if not isinstance(other, Version):
            return False
        return self.tuple == other.tuple

    def __lt__(self, other):
        if isinstance(other, Version):
            seq = other.tuple
        elif isinstance(other, Sequence):
            seq = tuple(other)
        else:
            raise ValueError("Comparison with non-Version object")
        return self.tuple < seq

    @property
    def tuple(self):
        return self.major, self.minor, self.patch


class Sequencer(BaseDevice):
    def __init__(self, name: str = "linuxpy client", **kwargs):
        self.name = name
        self.client_id = -1
        self.version: Optional[Version] = None
        self._local_ports = {}
        self.subscriptions = set()
        super().__init__(SEQUENCER_PATH, **kwargs)

    def __iter__(self):
        while True:
            yield from self.read()

    async def __aiter__(self):
        async with EventReader(self, max_queue_size=10) as reader:
            while True:
                for event in await reader.aread():
                    yield event

    def _on_open(self):
        self.client_id = read_client_id(self)
        client_info = read_client_info(self, self.client_id)
        self.version = Version.from_number(read_pversion(self))
        client_info.name = self.name.encode()
        write_client_info(self, client_info)

    def _on_close(self):
        # TODO: delete all open ports
        for port in self._local_ports.values():
            self.delete_port(port)

    @property
    def client_info(self):
        return read_client_info(self, self.client_id)

    @property
    def running_mode(self):
        return read_running_mode(self)

    @property
    def system_info(self):
        return read_system_info(self)

    @property
    def ports(self) -> Iterable["Port"]:
        for client in iter_read_clients(self):
            for port in iter_read_ports(self, client.client):
                yield Port(self, port)

    def create_port(
        self,
        name: str = "linuxpy port",
        capabilities: PortCapability = READ_WRITE,
        type: PortType = PortType.MIDI_GENERIC | PortType.APPLICATION,
    ) -> "Port":
        port_info = snd_seq_port_info()
        port_info.name = name.encode()
        port_info.addr.client = self.client_id
        port_info.capability = capabilities
        port_info.type = type
        port_info.midi_channels = 16
        port_info.midi_voices = 64
        port_info.synth_voices = 0
        create_port(self, port_info)
        port = Port(self, port_info)
        self._local_ports[port_info.addr.port] = port
        return port

    def delete_port(self, port: Union[int, "Port"]):
        if isinstance(port, int):
            addr = self.client_id, port
            port_info = snd_seq_port_info(addr=snd_seq_addr(client=self.client_id, port=port))
        else:
            port_info = port.info
            addr = port_info.addr.client, port_info.addr.port
        # unsubscribe first
        for uid in set(self.subscriptions):
            if addr == uid[0:2] or addr == uid[2:4]:
                self.unsubscribe(*uid)
        delete_port(self, port_info)

    def subscribe(self, src_client_id: int, src_port_id: int, dest_client_id: int, dest_port_id: int):
        uid = (src_client_id, src_port_id, dest_client_id, dest_port_id)
        self.subscriptions.add(uid)
        subscribe(self, src_client_id, src_port_id, dest_client_id, dest_port_id)

    def unsubscribe(self, src_client_id: int, src_port_id: int, dest_client_id: int, dest_port_id: int):
        uid = src_client_id, src_port_id, dest_client_id, dest_port_id
        self.subscriptions.remove(uid)
        unsubscribe(self, src_client_id, src_port_id, dest_client_id, dest_port_id)

    def iter_raw_read(self, max_nb_packets=64) -> Iterable["Event"]:
        payload = self._fobj.read(max_nb_packets * EVENT_SIZE)
        nb_packets = len(payload) // EVENT_SIZE
        i = 0
        while i < nb_packets:
            start = i * EVENT_SIZE
            packet = payload[start : start + EVENT_SIZE]
            event = Event(snd_seq_event.from_buffer_copy(packet))
            i += 1
            if event.is_variable_length_type:
                size = event.event.data.ext.len
                nb = (size + EVENT_SIZE - 1) // EVENT_SIZE
                event.data = payload[i * EVENT_SIZE : i * EVENT_SIZE + size]
                i += nb
            yield event

    def raw_read(self, max_nb_packets=64) -> Sequence["Event"]:
        return tuple(self.iter_raw_read(max_nb_packets=max_nb_packets))

    def wait_read(self) -> Sequence["Event"]:
        if self.io.select is not None:
            self.io.select((self,), (), ())
        return self.raw_read()

    def read(self) -> Sequence["Event"]:
        # first time we check what mode device was opened (blocking vs non-blocking)
        if self.is_blocking:
            self.read = self.raw_read
        else:
            self.read = self.wait_read
        return self.read()

    def write(self, event: "Event"):
        self._fobj.write(bytes(event))


class Port:
    def __init__(self, sequencer: Sequencer, port: snd_seq_port_info):
        self.sequencer = sequencer
        self.info = port

    @property
    def is_local(self):
        return self.sequencer.client_id == self.info.addr.client

    @property
    def client_id(self):
        return self.info.addr.client

    @property
    def port_id(self):
        return self.info.addr.port

    @property
    def type(self) -> PortType:
        return PortType(self.info.type)

    @property
    def capability(self) -> PortCapability:
        return PortCapability(self.info.capability)

    # MIDI In
    def connect_from(self, src_client_id, src_port_id):
        if not self.is_local:
            raise MidiError("Can only connect local port")
        self.sequencer.subscribe(src_client_id, src_port_id, self.client_id, self.port_id)

    def disconnect_from(self, src_client_id, src_port_id):
        if not self.is_local:
            raise MidiError("Can only connect local port")
        self.sequencer.unsubscribe(src_client_id, src_port_id, self.client_id, self.port_id)

    # MIDI Out
    def connect_to(self, dest_client_id, dest_port_id):
        if not self.is_local:
            raise MidiError("Can only connect local port")
        self.sequencer.subscribe(self.client_id, self.port_id, dest_client_id, dest_port_id)

    def disconnect_to(self, dest_client_id, dest_port_id):
        if not self.is_local:
            raise MidiError("Can only connect local port")
        self.sequencer.unsubscribe(self.client_id, self.port_id, dest_client_id, dest_port_id)

    def delete(self):
        if not self.is_local:
            raise MidiError("Can only delete local port")
        self.sequencer.delete_port(self)


EVENT_TYPE_INFO = {
    EventType.SYSTEM: ("System", "result"),
    EventType.RESULT: ("Result", "result"),
    EventType.NOTE: ("Note", "note"),
    EventType.NOTEON: ("Note on", "note"),
    EventType.NOTEOFF: ("Note off", "note"),
    EventType.KEYPRESS: ("Polyphonic aftertouch", "note"),
    EventType.CONTROLLER: ("Control change", "control"),
    EventType.PGMCHANGE: ("Program change", "control"),
    EventType.CHANPRESS: ("Channel aftertouch", "control"),
    EventType.PITCHBEND: ("Pitch bend", "control"),
    EventType.CONTROL14: ("Control change", "control"),
    EventType.NONREGPARAM: ("Non-reg. param.", "control"),
    EventType.REGPARAM: ("Reg param.", "control"),
    EventType.SONGPOS: ("Song position ptr", "control"),
    EventType.SONGSEL: ("Song select", "control"),
    EventType.QFRAME: ("MTC Quarter frame", "control"),
    EventType.TIMESIGN: ("SMF time signature", "control"),
    EventType.KEYSIGN: ("SMF key signature", "control"),
    EventType.START: ("Start", "queue"),
    EventType.CONTINUE: ("Continue", "queue"),
    EventType.STOP: ("Stop", "queue"),
    EventType.SETPOS_TICK: ("Set tick queue pos.", "queue"),
    EventType.SETPOS_TIME: ("Set rt queue pos.", "queue"),
    EventType.TEMPO: ("Set queue tempo", "queue"),
    EventType.CLOCK: ("Clock", "queue"),
    EventType.TICK: ("Tick", "queue"),
    EventType.QUEUE_SKEW: ("Queue timer skew", "queue"),
    EventType.TUNE_REQUEST: ("Tune request", None),
    EventType.RESET: ("Reset", None),
    EventType.SENSING: ("Active sensing", None),
    EventType.CLIENT_START: ("Client start", "addr"),
    EventType.CLIENT_EXIT: ("Client exit", "addr"),
    EventType.CLIENT_CHANGE: ("Client change", "addr"),
    EventType.PORT_START: ("Port start", "addr"),
    EventType.PORT_EXIT: ("Port exit", "addr"),
    EventType.PORT_CHANGE: ("Port change", "addr"),
    EventType.PORT_SUBSCRIBED: ("Port subscribed", "connect"),
    EventType.PORT_UNSUBSCRIBED: ("Port unsubscribed", "connect"),
    EventType.SYSEX: ("System exclusive", "ext"),
}


def struct_text(obj):
    fields = []
    for field_name, _, value in obj:
        if isinstance(value, Struct):
            value = f"({struct_text(value)})"
        elif isinstance(value, ctypes.Union):
            continue
        else:
            value = str(value)
        fields.append(f"{field_name}={value}")
    return ", ".join(fields)


class Event:
    def __init__(self, event: snd_seq_event):
        self.event = event
        self.data = b""

    def __repr__(self):
        cname = type(self).__name__
        return f"<{cname} type={self.type.name}>"

    def __str__(self):
        data = EVENT_TYPE_INFO.get(self.type)
        if data is None:
            return self.type.name
        name, member_name = data
        src = f"{self.source_client_id:>3}:{self.source_port_id:<3}"
        result = f"{src} {name:<20} "
        if self.type == EventType.SYSEX:
            result += " ".join(f"{i:02X}" for i in self.data)
        elif member_name:
            member = getattr(self.event.data, member_name)
            result += struct_text(member)
        return result

    @classmethod
    def new(cls, etype: Union[str, int, EventType], **kwargs):
        event = snd_seq_event()
        if isinstance(etype, int):
            etype = EventType(etype)
        elif isinstance(etype, str):
            etype = etype.replace(" ", "").replace("_", "").upper()
            try:
                etype = EventType[etype]
            except KeyError:
                pass
        event.type = etype
        event_info = EVENT_TYPE_INFO.get(etype)
        if event_info:
            _, member_name = event_info
            member = getattr(event.data, member_name)
            allowed = {name for name, _ in member._fields_}
            not_allowed = set(kwargs) - allowed
            if not_allowed:
                raise ValueError(f"These fields are not allowed for {etype.name}: {', '.join(not_allowed)}")
            for key, value in kwargs.items():
                setattr(member, key, value)
        return cls(event)

    @property
    def type(self) -> EventType:
        return EventType(self.event.type)

    @property
    def length_type(self) -> EventLength:
        return EventLength(self.event.flags & EventLength.MASK.value)

    @property
    def is_variable_length_type(self) -> bool:
        return self.length_type == EventLength.VARIABLE

    @property
    def timestamp_type(self) -> TimeStamp:
        return TimeStamp(self.event.flags & TimeStamp.MASK.value)

    @property
    def time_mode(self) -> TimeMode:
        return TimeMode(self.event.flags & TimeMode.MASK.value)

    @property
    def timestamp(self) -> Union[float, int]:
        if self.timestamp_type == TimeStamp.REAL:
            return self.event.data.time.time.tv_sec + self.event.data.time.time.tv_nsec * 1e-9
        else:
            return self.event.data.time.tick

    @property
    def note(self):
        return self.event.data.note

    @property
    def control(self):
        return self.event.data.control

    @property
    def connect(self):
        return self.event.data.connect

    @property
    def source_client_id(self) -> int:
        return self.event.source.client

    @property
    def source_port_id(self) -> int:
        return self.event.source.port

    @property
    def dest_client_id(self) -> int:
        return self.event.dest.client

    @property
    def dest_port_id(self) -> int:
        return self.event.dest.port

    client_id = source_client_id
    port_id = source_port_id


class EventReader:
    def __init__(self, device: Sequencer, max_queue_size=1):
        self.device = device
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._selector: Optional[select.epoll] = None
        self._buffer: Optional[asyncio.Queue] = None
        self._max_queue_size = max_queue_size

    async def __aenter__(self):
        if self.device.is_blocking:
            raise MidiError("Cannot use async event reader on blocking device")
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
            data = self.device.read()
            task.set_result(data)
        except Exception as error:
            task.set_exception(error)

        buffer = self._buffer
        if buffer.full():
            self.device.log.warn("missed event")
            buffer.get_nowait()
        buffer.put_nowait(task)

    def read(self, timeout=None):
        return self.device.read()

    async def aread(self):
        """Wait for next event or return last event"""
        task = await self._buffer.get()
        return await task


def event_stream(seq):
    while True:
        yield from seq.read()


async def async_event_stream(seq, maxsize=10):
    queue = asyncio.Queue(maxsize=maxsize)

    def feed():
        for event in seq.read():
            queue.put_nowait(event)

    with add_reader_asyncio(seq.fileno(), feed):
        while True:
            yield await queue.get()


if __name__ == "__main__":
    seq = Sequencer()
    seq.open()
