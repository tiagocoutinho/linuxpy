#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import asyncio
import errno
import itertools
from enum import IntEnum

from linuxpy import ctypes
from linuxpy.ctypes import Struct, cint, cvoidp, sizeof
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
    snd_seq_query_subs,
    snd_seq_queue_client,
    snd_seq_queue_info,
    snd_seq_queue_status,
    snd_seq_running_info,
    snd_seq_system_info,
)
from linuxpy.types import Iterable, Optional, Sequence, Union
from linuxpy.util import add_reader_asyncio

ALSA_PATH = DEV_PATH / "snd"
SEQUENCER_PATH = ALSA_PATH / "seq"


class RealtimeStatusCode(IntEnum):
    REALTIME = 0xF0
    SYSEX_START = 0xF0
    MIDI_TIME_CODE = 0xF1
    SONG_POSITION = 0xF2
    SONG_SELECT = 0xF3
    TUNE_REQUEST = 0xF6
    SYSEX_END = 0xF7
    TIMING_CLOCK = 0xF8
    START = 0xFA
    CONTINUE = 0xFB
    STOP = 0xFC
    ACTIVE_SENSING = 0xFE
    RESET = 0xFF


#: unknown source
ADDRESS_UNKNOWN = 253

#: direct dispatch
QUEUE_DIRECT = 253

#: send event to all subscribed ports
ADDRESS_SUBSCRIBERS = 254

#: send event to all queues/clients/ports/channels
ADDRESS_BROADCAST = 255

SUBSCRIBERS = (ADDRESS_SUBSCRIBERS, ADDRESS_UNKNOWN)
BROADCAST = (ADDRESS_BROADCAST, ADDRESS_BROADCAST)

#: size of event (bytes)
EVENT_SIZE = sizeof(snd_seq_event)

#: READ + SUBSCRIBE READ port capabilities
READ = PortCapability.READ | PortCapability.SUBS_READ

#: WRITE + SUBSCRIBE WRITE port capabilities
WRITE = PortCapability.WRITE | PortCapability.SUBS_WRITE

#: full READ + WRITE port capabilities
READ_WRITE = READ | WRITE


PortT = Union[int, "Port"]
AddressT = Union[snd_seq_addr, tuple[int, PortT]]
EventT = Union[str, int, EventType]
AddressesT = Sequence[AddressT]


class MidiError(Exception):
    pass


def read_pversion(seq) -> int:
    return ioctl(seq, IOC.PVERSION, cint()).value


def read_system_info(seq) -> snd_seq_system_info:
    return ioctl(seq, IOC.SYSTEM_INFO, snd_seq_system_info())


def read_running_mode(seq) -> snd_seq_running_info:
    return ioctl(seq, IOC.RUNNING_MODE, snd_seq_running_info())


def read_client_id(seq) -> int:
    return ioctl(seq, IOC.CLIENT_ID, cint()).value


def read_client_info(seq, client_id: int) -> snd_seq_client_info:
    return ioctl(seq, IOC.GET_CLIENT_INFO, snd_seq_client_info(client=client_id))


def write_client_info(seq, client: snd_seq_client_info):
    return ioctl(seq, IOC.SET_CLIENT_INFO, client)


def next_client(seq, client_id: int) -> Optional[snd_seq_client_info]:
    try:
        return ioctl(seq, IOC.QUERY_NEXT_CLIENT, snd_seq_client_info(client=client_id))
    except FileNotFoundError:
        pass


def iter_read_clients(seq) -> Iterable[snd_seq_client_info]:
    next_client_id = -1
    while client := next_client(seq, next_client_id):
        yield client
        next_client_id = client.client


def read_port_info(seq, client_id: int, port_id: int) -> snd_seq_port_info:
    port = snd_seq_port_info(client=client_id)
    port.addr.client = client_id
    port.addr.port = port_id
    return ioctl(seq, IOC.GET_PORT_INFO, port)


def next_port(seq, client_id: int, port_id: int) -> Optional[snd_seq_port_info]:
    port = snd_seq_port_info(client=client_id)
    port.addr.client = client_id
    port.addr.port = port_id
    try:
        return ioctl(seq, IOC.QUERY_NEXT_PORT, port)
    except FileNotFoundError:
        pass


def iter_read_ports(seq, client_id: int) -> Iterable[snd_seq_port_info]:
    next_port_id = -1
    while port := next_port(seq, client_id, next_port_id):
        yield port
        next_port_id = port.addr.port


def create_port(seq, port: snd_seq_port_info):
    return ioctl(seq, IOC.CREATE_PORT, port)


def delete_port(seq, port: snd_seq_port_info):
    return ioctl(seq, IOC.DELETE_PORT, port)


def subscribe(seq, src: AddressT, dest: AddressT):
    subs = snd_seq_port_subscribe()
    subs.sender = to_address(src)
    subs.dest = to_address(dest)
    return ioctl(seq, IOC.SUBSCRIBE_PORT, subs)


def unsubscribe(seq, src: AddressT, dest: AddressT):
    subs = snd_seq_port_subscribe()
    subs.sender = to_address(src)
    subs.dest = to_address(dest)
    return ioctl(seq, IOC.UNSUBSCRIBE_PORT, subs)


def iter_read_subscribers(seq, client_id: int, port_id: int):
    for i in itertools.count():
        value = snd_seq_query_subs()
        value.root.client = client_id
        value.root.port = port_id
        value.index = i
        ioctl(seq, IOC.QUERY_SUBS, value)
        if value.index == value.num_subs:
            break
        yield value
        if value.index + 1 == value.num_subs:
            break


def create_queue(seq) -> snd_seq_queue_info:
    return ioctl(seq, IOC.CREATE_QUEUE, snd_seq_queue_info())


def delete_queue(seq, queue: int) -> snd_seq_queue_info:
    return ioctl(seq, IOC.DELETE_QUEUE, snd_seq_queue_info(queue=queue))


def write_queue_info(seq, queue: snd_seq_queue_info):
    return ioctl(seq, IOC.SET_QUEUE_INFO, queue)


def read_queue_status(seq, queue: int):
    return ioctl(seq, IOC.GET_QUEUE_STATUS, snd_seq_queue_status(queue=queue))


def read_queue_client(seq, queue: int):
    return ioctl(seq, IOC.GET_QUEUE_CLIENT, snd_seq_queue_client(queue=queue))


def to_address(addr: AddressT) -> snd_seq_addr:
    """Convert to low level snd_seq_addr"""
    if isinstance(addr, snd_seq_addr):
        return addr
    return snd_seq_addr(*map(int, addr))


def to_event_type(event_type: EventT) -> EventType:
    if isinstance(event_type, EventType):
        return event_type
    elif isinstance(event_type, int):
        return EventType(event_type)
    else:
        try:
            event_type = event_type.upper().replace(" ", "_")
            return EventType[event_type]
        except KeyError:
            event_type = event_type.replace("_", "").upper()
            return EventType[event_type]


class Version:
    def __init__(self, major: int, minor: int, patch: int):
        self.major = major
        self.minor = minor
        self.patch = patch

    @classmethod
    def from_tuple(cls, sequence: Iterable[Union[str, int]]):
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
            raise ValueError("Comparison with non-Version object")
        return self.tuple == other.tuple

    def __lt__(self, other):
        if not isinstance(other, Version):
            raise ValueError("Comparison with non-Version object")
        return self.tuple < other.tuple

    def __le__(self, other):
        return self == other or self < other

    def __gt__(self, other):
        return not self <= other

    def __ge__(self, other):
        return not self < other

    @property
    def tuple(self):
        return self.major, self.minor, self.patch


class Sequencer(BaseDevice):
    def __init__(self, name: str = "linuxpy client", **kwargs):
        self.name = name
        self.client_id = -1
        self.version: Optional[Version] = None
        self._local_ports = set()
        self.subscriptions = set()
        super().__init__(SEQUENCER_PATH, **kwargs)

    def __iter__(self):
        return event_stream(self)

    async def __aiter__(self):
        async for event in async_event_stream(self, maxsize=10):
            yield event

    def _on_open(self):
        self.client_id = read_client_id(self)
        client_info = read_client_info(self, self.client_id)
        self.version = Version.from_number(read_pversion(self))
        client_info.name = self.name.encode()
        write_client_info(self, client_info)

    def _on_close(self):
        # TODO: delete all open ports
        for port in set(self._local_ports):
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
    def iter_ports(self) -> Iterable["Port"]:
        for client in iter_read_clients(self):
            for port in iter_read_ports(self, client.client):
                yield Port(self, port)

    @property
    def ports(self) -> Sequence["Port"]:
        return list(self.iter_ports)

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
        self._local_ports.add(port_info.addr.port)
        return port

    def delete_port(self, port: Union[int, "Port"]):
        if isinstance(port, int):
            addr = self.client_id, port
            port_info = snd_seq_port_info(addr=snd_seq_addr(client=self.client_id, port=port))
        else:
            port_info = port.info
            if port_info.addr.client != self.client_id:
                raise MidiError("Cannot delete non local port")
            addr = port_info.addr.client, port_info.addr.port
        # unsubscribe first
        for uid in set(self.subscriptions):
            if addr == uid[0:2] or addr == uid[2:4]:
                self.unsubscribe(uid[0:2], uid[2:4])
        self._local_ports.remove(addr[1])
        delete_port(self, port_info)

    def subscribe(self, src: AddressT, dest: AddressT):
        src = to_address(src)
        dest = to_address(dest)
        uid = (src.client, src.port, dest.client, dest.port)
        self.subscriptions.add(uid)
        subscribe(self, src, dest)

    def unsubscribe(self, src: AddressT, dest: AddressT):
        src = to_address(src)
        dest = to_address(dest)
        uid = (src.client, src.port, dest.client, dest.port)
        self.subscriptions.remove(uid)
        try:
            unsubscribe(self, src, dest)
        except OSError as error:
            if error.errno == errno.ENXIO:
                self.log.info("Could not delete port (maybe device was unplugged)")
            else:
                raise

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
                event.data = payload[i * EVENT_SIZE : i * EVENT_SIZE + size][1:-1]
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

    def send(
        self,
        port: PortT,
        event_type: Union[str, int, EventType],
        queue: int = QUEUE_DIRECT,
        to: Union[AddressT, AddressesT] = SUBSCRIBERS,
        **kwargs,
    ):
        """
        Send a message from a specific port to the destination address(es)

        event_type can be an instance of EventType or the equivalent number or
        a string matching the event type (ex: "noteon", "NOTEON" "note)
        """
        event = Event.new(event_type, **kwargs)
        event.queue = queue
        event.source = to_address((self.client_id, port))
        if isinstance(to, Sequence) and isinstance(to[0], Sequence):
            to_list = to
        else:
            to_list = (to,)
        for dest in to_list:
            event.dest = to_address(dest)
            self.write(event)


class Port:
    def __init__(self, sequencer: Sequencer, port: snd_seq_port_info):
        self.sequencer = sequencer
        self.info = port

    def __repr__(self):
        prefix = self.is_local and "Local" or ""
        name = f"{prefix}{type(self).__name__}"
        client = self.client_id
        port = self.port_id
        ptype = str(self.type).split(".", 1)[-1]
        caps = str(self.capability).split(".", 1)[-1]
        return f"<{name} {client=}, {port=}, type={ptype}, {caps=}>"

    def __str__(self):
        ptype = str(self.type).split(".", 1)[-1]
        caps = str(self.capability).split(".", 1)[-1]
        return f"{self.client_id:3}:{self.port_id:<3}  {self.name}  {ptype}  {caps}"

    def __int__(self):
        return self.port_id

    @property
    def name(self) -> str:
        return self.info.name.decode()

    @property
    def is_local(self) -> bool:
        return self.sequencer.client_id == self.info.addr.client

    @property
    def client_id(self) -> int:
        return self.info.addr.client

    @property
    def port_id(self) -> int:
        return self.info.addr.port

    @property
    def type(self) -> PortType:
        return PortType(self.info.type)

    @property
    def capability(self) -> PortCapability:
        return PortCapability(self.info.capability)

    @property
    def address(self) -> snd_seq_addr:
        return self.info.addr

    # MIDI In
    def connect_from(self, src: AddressT):
        if not self.is_local:
            raise MidiError("Can only connect local port")
        self.sequencer.subscribe(src, self.address)

    def disconnect_from(self, src: AddressT):
        if not self.is_local:
            raise MidiError("Can only disconnect local port")
        self.sequencer.unsubscribe(src, self.address)

    # MIDI Out
    def connect_to(self, dest: AddressT):
        if not self.is_local:
            raise MidiError("Can only connect local port")
        self.sequencer.subscribe(self.address, dest)

    def disconnect_to(self, dest):
        if not self.is_local:
            raise MidiError("Can only disconnect local port")
        self.sequencer.unsubscribe(self.address, dest)

    def delete(self):
        if not self.is_local:
            raise MidiError("Can only delete local port")
        self.sequencer.delete_port(self)

    def send(self, event_type: Union[str, int, EventType], **kwargs):
        self.sequencer.send(self, event_type, **kwargs)


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
    SIXEX_START = RealtimeStatusCode.SYSEX_START.to_bytes(1, "big")
    SIXEX_END = RealtimeStatusCode.SYSEX_END.to_bytes(1, "big")

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
        addr = f"{self.source_client_id:}:{self.source_port_id:} {self.dest_client_id:}:{self.dest_port_id:}"
        result = f"{addr} {name} "
        if self.type == EventType.SYSEX:
            result += " ".join(f"{i:02X}" for i in self.raw_data)
        elif self.type == EventType.CLOCK:
            queue_ctrl = self.queue_ctrl
            real_time = queue_ctrl.param.time.time
            timestamp = real_time.tv_sec + real_time.tv_nsec * 1e-9
            result += f"queue={queue_ctrl.queue} {timestamp=}"
        elif member_name:
            member = getattr(self.event.data, member_name)
            result += struct_text(member)
        return result

    def __bytes__(self):
        if self.type == EventType.SYSEX:
            self.event.flags = EventLength.VARIABLE
        if self.is_variable_length_type:
            data = self.raw_data
            self.event.data.ext.len = len(data)
            self.event.data.ext.ptr = cvoidp()
            return bytes(self.event) + data
        else:
            return bytes(self.event)

    @classmethod
    def new(cls, etype: EventT, **kwargs):
        data = kwargs.pop("data", b"")
        event = snd_seq_event()
        etype = to_event_type(etype)
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
        result = cls(event)
        result.data = data
        return result

    @property
    def raw_data(self) -> bytes:
        if self.type == EventType.SYSEX and not self.data.startswith(self.SIXEX_START):
            return self.SIXEX_START + self.data + self.SIXEX_END
        return self.data

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
    def queue_ctrl(self):
        return self.event.data.queue

    @property
    def source(self) -> snd_seq_addr:
        return self.event.source

    @source.setter
    def source(self, address: AddressT):
        self.event.source = to_address(address)

    @property
    def dest(self) -> snd_seq_addr:
        return self.event.dest

    @dest.setter
    def dest(self, address: AddressT):
        self.event.dest = to_address(address)

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

    @property
    def queue(self):
        return self.event.queue

    @queue.setter
    def queue(self, queue: int):
        self.event.queue = queue

    client_id = source_client_id
    port_id = source_port_id


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
