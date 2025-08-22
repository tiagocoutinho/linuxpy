#
# This file is part of the linuxpy project
#
# Copyright (c) 2024 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import dataclasses
import errno
import pathlib
from collections import namedtuple
from collections.abc import Iterable
from pathlib import Path

from linuxpy.ctypes import POINTER, cast, cvoidp
from linuxpy.device import BaseDevice, iter_device_files
from linuxpy.ioctl import ioctl
from linuxpy.types import PathLike
from linuxpy.util import Version, make_find

from . import raw

DeviceInfo = namedtuple("DeviceInfo", "driver model serial bus_info media_version hw_revision driver_version")

EntityFlag = raw.EntityFlag
EntityFunction = raw.EntityFunction
InterfaceType = raw.InterfaceType
PadFlag = raw.PadFlag
LinkFlag = raw.LinkFlag


@dataclasses.dataclass
class BaseElement:
    id: int
    topology: "Topology" = dataclasses.field(repr=False)

    def __int__(self) -> int:
        return self.id

    @property
    def links(self) -> list["Link"]:
        links = self.topology.links.values()
        return [link for link in links if link.sink_id == self.id or link.source_id == self.id]


@dataclasses.dataclass
class Entity(BaseElement):
    name: str
    type: EntityFunction
    flags: EntityFlag

    @property
    def interface(self):
        for link in self.topology.links.values():
            if link.sink_id == self.id:
                if interface := self.topology.interfaces.get(link.source_id):
                    return interface

    @property
    def pads(self):
        pads = self.topology.pads.values()
        return [pad for pad in pads if pad.entity_id == self.id]

    @property
    def text(self):
        flags = self.flags.name if self.flags else 0
        pads = "\n".join(pad.text for pad in self.pads)
        pads = "    " + pads.replace("\n", "\n    ")
        if interface := self.interface:
            node = f", node={interface.dev_path}"
        else:
            node = ""
        return f"""Entity {self.id}: {self.name} type={self.type.name} {flags=}{node})\n{pads}"""


@dataclasses.dataclass
class Interface(BaseElement):
    type: InterfaceType
    flags: int
    devnode: tuple[int, int]

    @property
    def entities(self) -> list[Entity]:
        links = self.topology.links.values()
        return [self.topology.entities[link.sink_id] for link in links if link.source_id == self.id]

    @property
    def text(self):
        return f"""Interface (type={self.type.name}, flags={self.flags}, node={self.dev_path})"""

    @property
    def dev_path(self):
        node = f"{self.devnode[0]}:{self.devnode[1]}"
        with pathlib.Path(f"/sys/dev/char/{node}/uevent").open() as fobj:
            for line in fobj:
                if line.startswith("DEVNAME="):
                    name = line.split("=", 1)[-1].strip()
                    return pathlib.Path("/dev", name)


@dataclasses.dataclass
class Pad(BaseElement):
    entity_id: int
    flags: PadFlag
    index: int

    @property
    def entity(self) -> Entity:
        return self.topology.entities[self.entity_id]

    def _link_text(self, link):
        sink = self.flags == PadFlag.SINK
        other_pad = link.source if sink else link.sink
        other_entity = other_pad.entity
        other_name = other_entity.name
        direction = "<-" if sink else "->"
        return f"{direction} {other_name}:{self.index} {link.flags.name}"

    @property
    def text(self):
        links = "\n".join(self._link_text(link) for link in self.links)
        links = "    " + links.replace("\n", "\n    ")
        return f"""Pad ({self.flags.name.capitalize()}):\n{links}"""


@dataclasses.dataclass
class Link(BaseElement):
    source_id: int
    sink_id: int
    flags: LinkFlag

    @property
    def source(self) -> Entity | Interface | Pad:
        return self.topology[self.source_id]

    @property
    def sink(self) -> Entity | Interface | Pad:
        return self.topology[self.sink_id]


@dataclasses.dataclass
class Topology:
    version: int
    entities: dict[int, Entity] = dataclasses.field(default_factory=dict)
    interfaces: dict[int, Interface] = dataclasses.field(default_factory=dict)
    pads: dict[int, Pad] = dataclasses.field(default_factory=dict)
    links: dict[int, Link] = dataclasses.field(default_factory=dict)

    @property
    def text(self):
        entities = [entity.text for entity in self.entities.values()]
        return "\n\n".join(entities)

    def __getitem__(self, id):
        for col in (self.entities, self.interfaces, self.pads, self.links):
            try:
                return col[id]
            except KeyError:
                pass
        raise KeyError(id)


EntityDesc = namedtuple("EntityDesc", "id name type flags pads outbound_links devnode")
PadDesc = namedtuple("PadDesc", "entity_id flags index")
LinkDesc = namedtuple("LinkDesc", "source sink flags")


def entity_has_flags(version: int):
    return (version) >= ((4 << 16) | (19 << 8) | 0)


def _translate_topology(topology: raw.media_v2_topology) -> Topology:
    top = Topology(version=topology.topology_version)

    ptr_entities = cast(topology.ptr_entities, POINTER(raw.media_v2_entity))
    ptr_interfaces = cast(topology.ptr_interfaces, POINTER(raw.media_v2_interface))
    ptr_pads = cast(topology.ptr_pads, POINTER(raw.media_v2_pad))
    ptr_links = cast(topology.ptr_links, POINTER(raw.media_v2_link))

    top.entities |= {
        entity.id: Entity(
            entity.id, top, entity.name.decode(), EntityFunction(entity.function), EntityFlag(entity.flags)
        )
        for entity in ptr_entities[: topology.num_entities]
    }

    top.interfaces = {
        interface.id: Interface(
            interface.id, top, InterfaceType(interface.intf_type), 0, (interface.devnode.major, interface.devnode.minor)
        )
        for interface in ptr_interfaces[: topology.num_interfaces]
    }

    top.pads = {
        pad.id: Pad(pad.id, top, pad.entity_id, PadFlag(pad.flags), pad.index) for pad in ptr_pads[: topology.num_pads]
    }

    top.links = {
        link.id: Link(link.id, top, link.source_id, link.sink_id, raw.LinkFlag(link.flags))
        for link in ptr_links[: topology.num_links]
    }

    return top


def get_raw_topology(fd) -> raw.media_v2_topology:
    topology = raw.media_v2_topology()
    # initial call to get nb of entities, interfaces, pads and links
    ioctl(fd, raw.IOC.G_TOPOLOGY, topology)
    version = topology.topology_version

    entities = (topology.num_entities * raw.media_v2_entity)()
    interfaces = (topology.num_interfaces * raw.media_v2_interface)()
    pads = (topology.num_pads * raw.media_v2_pad)()
    links = (topology.num_links * raw.media_v2_link)()
    topology.ptr_entities = cast(entities, cvoidp).value
    topology.ptr_interfaces = cast(interfaces, cvoidp).value
    topology.ptr_pads = cast(pads, cvoidp).value
    topology.ptr_links = cast(links, cvoidp).value

    # second call to get all information
    ioctl(fd, raw.IOC.G_TOPOLOGY, topology)
    assert version == topology.topology_version
    return topology


def get_topology(fd) -> Topology:
    topology = get_raw_topology(fd)
    return _translate_topology(topology)


def _translate_device_info(info: raw.media_device_info) -> DeviceInfo:
    return DeviceInfo(
        info.driver.decode(),
        info.model.decode(),
        info.serial.decode(),
        info.bus_info.decode(),
        Version.from_number(info.media_version),
        info.hw_revision,
        Version.from_number(info.driver_version),
    )


def get_raw_device_info(fd) -> raw.media_device_info:
    info = raw.media_device_info()
    return ioctl(fd, raw.IOC.DEVICE_INFO, info)


def get_device_info(fd):
    info = get_raw_device_info(fd)
    return _translate_device_info(info)


def iter_read(fd, ioc, indexed_struct, start=0, stop=128, step=1):
    for index in range(start, stop, step):
        indexed_struct.index = index
        try:
            ioctl(fd, ioc, indexed_struct)
            yield indexed_struct
        except OSError as error:
            if error.errno == errno.EINVAL:
                break
            else:
                raise


def iter_entities(fd):
    for raw_entity_desc in iter_read(fd, raw.IOC.ENUM_ENTITIES, raw.media_entity_desc(id=raw.ENTITY_ID_FLAG_NEXT)):
        links = raw.media_links_enum(entity=raw_entity_desc.id)
        links.pads = (raw_entity_desc.pads * raw.media_pad_desc)()
        links.links = (raw_entity_desc.links * raw.media_link_desc)()
        ioctl(fd, raw.IOC.ENUM_LINKS, links)
        pads = [PadDesc(pad.entity, raw.PadFlag(pad.flags), pad.index) for pad in links.pads[: raw_entity_desc.pads]]
        links = [
            LinkDesc(
                PadDesc(link.source.entity, raw.PadFlag(link.source.flags), link.source.index),
                PadDesc(link.sink.entity, raw.PadFlag(link.sink.flags), link.sink.index),
                raw.LinkFlag(link.flags),
            )
            for link in links.links[: raw_entity_desc.links]
        ]
        func = raw_entity_desc.type
        yield EntityDesc(
            raw_entity_desc.id,
            raw_entity_desc.name.decode(),
            EntityFunction(func) if func in EntityFunction else func,
            raw.EntityFlag(raw_entity_desc.flags),
            pads,
            links,
            (raw_entity_desc.dev.major, raw_entity_desc.dev.minor),
        )
        raw_entity_desc.id |= raw.ENTITY_ID_FLAG_NEXT


def setup_link(
    fd, source_entity_id: int, source_pad_index: int, sink_entity_id: int, sink_pad_index: int, enabled: bool
):
    link = raw.media_link_desc()
    link.source.entity = source_entity_id
    link.source.index = source_pad_index
    link.sink.entity = sink_entity_id
    link.sink.index = sink_pad_index
    link.flags = raw.LinkFlag.ENABLED if enabled else 0
    ioctl(fd, raw.IOC.SETUP_LINK, link)


REPR = """\
Media controller API version {info.media_version}

Media device information
------------------------
driver          {info.driver}
model           {info.model}
serial          {info.serial}
bus info        {info.bus_info}
hw revision     0x{info.hw_revision:x}
driver version  {info.driver_version}

Device topology
{topology}
"""


class Device(BaseDevice):
    PREFIX = "/dev/media"

    def get_topology(self):
        return get_topology(self)

    def get_device_info(self):
        return get_device_info(self)

    @property
    def text(self):
        if self.closed:
            return f"Media {self.filename}"
        info = self.get_device_info()
        topology = self.get_topology()
        return REPR.format(info=info, topology=topology.text)


def iter_media_files(path: PathLike = "/dev") -> Iterable[Path]:
    """Returns an iterator over all media files"""
    return iter_device_files(path=path, pattern="media*")


def iter_devices(path: PathLike = "/dev", **kwargs) -> Iterable[Device]:
    """Returns an iterator over all media devices"""
    return (Device(name, **kwargs) for name in iter_media_files(path=path))


find = make_find(iter_devices)
