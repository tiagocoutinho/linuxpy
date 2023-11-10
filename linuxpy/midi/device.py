import asyncio
import select

from linuxpy.ctypes import cint, sizeof
from linuxpy.device import DEV_PATH, BaseDevice
from linuxpy.ioctl import ioctl
from linuxpy.midi.raw import (
    IOC,
    EventType,
    PortCapability,
    PortType,
    snd_seq_client_info,
    snd_seq_event,
    snd_seq_port_info,
    snd_seq_port_subscribe,
    snd_seq_running_info,
    snd_seq_system_info,
)
from linuxpy.types import Iterable, Optional
from linuxpy.util import add_reader_asyncio

ALSA_PATH = DEV_PATH / "snd"
SEQUENCER_PATH = ALSA_PATH / "seq"


EVENT_SIZE = sizeof(snd_seq_event)


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


def print_port(client, port):
    cname = client.name.decode()
    pname = port.name.decode()
    caps = repr(PortCapability(port.capability))
    caps = caps.removeprefix("<PortCapability.").rsplit(":", 1)[0]
    print(f" {port.addr.client:2}:{port.addr.port}  {cname:<24}  {pname:<24}  {caps}")


def print_client_ports(client, ports):
    for port in ports:
        print_port(client, port)


def print_ports(seq):
    for client in iter_read_clients(seq):
        print_client_ports(client, iter_read_ports(seq, client.client))


def create_port(seq, port: snd_seq_port_info):
    ioctl(seq, IOC.CREATE_PORT, port)


def delete_port(seq, port: snd_seq_port_info):
    ioctl(seq, IOC.DELETE_PORT, port)


def version_tuple(version_number):
    return ((version_number >> 16) & 0xFF, (version_number >> 8) & 0xFF, (version_number) & 0xFF)


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
    def __init__(self, number: int):
        self.number = number

    def __int__(self):
        return self.number

    @property
    def tuple(self):
        return version_tuple(self.number)

    def __str__(self):
        return "{}.{}.{}".format(*self.tuple)


class Sequencer(BaseDevice):
    def __init__(self, name: str = "linuxpy client", **kwargs):
        self.name = name
        self.client_id: Optional[int] = None
        self.version: Optional[Version] = None
        self.ports = {}
        super().__init__(SEQUENCER_PATH, **kwargs)

    def _on_open(self):
        self.client_id = read_client_id(self)
        client_info = read_client_info(self, self.client_id)
        self.version_number = Version(read_pversion(self))
        client_info.name = self.name.encode()
        write_client_info(self, client_info)

    def _on_close(self):
        # TODO: delete all open ports
        for port in self.ports.values():
            delete_port(self, port.info)

    @property
    def client_info(self):
        return read_client_info(self, self.client_id)

    @property
    def running_mode(self):
        return read_running_mode(self)

    @property
    def system_info(self):
        return read_system_info(self)

    def create_port(self, name: str = "linuxpy port") -> "Port":
        port_info = snd_seq_port_info()
        port_info.name = name.encode()
        port_info.addr.client = self.client_id
        port_info.capability = PortCapability.WRITE | PortCapability.SUBS_WRITE
        port_info.type = PortType.MIDI_GENERIC | PortType.APPLICATION
        port_info.midi_channels = 16
        port_info.midi_voices = 64
        port_info.synth_voices = 0
        create_port(self, port_info)
        port = Port(self, port_info)
        self.ports[port_info.addr.port] = port
        return port

    def raw_read(self) -> snd_seq_event:
        event = snd_seq_event()
        self._fobj.readinto(event)
        return event

    def wait_read(self) -> snd_seq_event:
        if self.io.select is not None:
            self.io.select((self,), (), ())
        return self.raw_read()

    def read(self) -> snd_seq_event:
        # first time we check what mode device was opened (blocking vs non-blocking)
        # if file was opened with O_NONBLOCK: DQBUF will not block until a buffer
        # is available for read. So we need to do it here
        if self.is_blocking:
            self.read = self.raw_read
        else:
            self.read = self.wait_read
        return self.read()

    async def aread(self):
        ...


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

    # MIDI In
    def connect_from(self, src_client_id, src_port_id):
        if not self.is_local:
            raise MidiError("Can only connect local port")
        subscribe(self.sequencer, src_client_id, src_port_id, self.client_id, self.port_id)

    def disconnect_from(self, src_client_id, src_port_id):
        if not self.is_local:
            raise MidiError("Can only connect local port")
        unsubscribe(self.sequencer, src_client_id, src_port_id, self.client_id, self.port_id)

    # MIDI Out
    def connect_to(self, dest_client_id, dest_port_id):
        if not self.is_local:
            raise MidiError("Can only connect local port")
        subscribe(self.sequencer, self.client_id, self.port_id, dest_client_id, dest_port_id)

    def disconnect_to(self, dest_client_id, dest_port_id):
        if not self.is_local:
            raise MidiError("Can only connect local port")
        unsubscribe(self.sequencer, self.client_id, self.port_id, dest_client_id, dest_port_id)


class Message:
    def __init__(self, event: snd_seq_event):
        self.event = event

    @property
    def type(self):
        return EventType(self.event.type)


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
            data = self.device.raw_read()
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
        return self.device.raw_read()

    async def aread(self):
        """Wait for next event or return last event"""
        task = await self._buffer.get()
        return await task


def event_stream(seq):
    while True:
        seq.io.select((seq,), (), ())
        yield seq.raw_read()


async def async_event_stream(seq, maxsize=1000):
    queue = asyncio.Queue(maxsize=maxsize)
    with add_reader_asyncio(seq.fileno(), lambda: queue.put_nowait(seq.raw_read())):
        while True:
            yield await queue.get()


if __name__ == "__main__":
    seq = Sequencer()
    seq.open()
