#
# This file is part of the linuxpy project
#
# Copyright (c) 2024 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import collections
import errno
from collections.abc import Iterable
from pathlib import Path

from linuxpy.ctypes import POINTER, cast, cvoidp
from linuxpy.device import BaseDevice, iter_device_files
from linuxpy.ioctl import ioctl
from linuxpy.types import PathLike
from linuxpy.util import make_find

from . import raw

Entity = collections.namedtuple("Entity", "id name type flags")

Interface = collections.namedtuple("Interface", "id type flags devnode")
Pad = collections.namedtuple("Pad", "id entity_id flags index")
Link = collections.namedtuple("Link", "id source_id sink_id flags")
Topology = collections.namedtuple("Topology", "version entities interfaces pads links")
DeviceInfo = collections.namedtuple(
    "DeviceInfo", "driver model serial bus_info media_version hw_revision driver_version"
)
EntityDesc = collections.namedtuple("EntityDesc", "id name type flags pads outbound_links devnode")
PadDesc = collections.namedtuple("PadDesc", "entity_id flags index")
LinkDesc = collections.namedtuple("LinkDesc", "source sink flags")

EntityFunction = raw.EntityFunction


def entity_has_flags(version: int):
    return (version) >= ((4 << 16) | (19 << 8) | 0)


def _translate_topology(topology: raw.media_v2_topology) -> Topology:
    # has_flags = entity_has_flags(topology.topology_version)

    ptr_entities = cast(topology.ptr_entities, POINTER(raw.media_v2_entity))
    entities = [
        Entity(entity.id, entity.name.decode(), raw.EntityFunction(entity.function), raw.EntityFlag(entity.flags))
        for entity in ptr_entities[: topology.num_entities]
    ]
    ptr_interfaces = cast(topology.ptr_interfaces, POINTER(raw.media_v2_interface))
    interfaces = [
        Interface(
            interface.id, raw.InterfaceType(interface.intf_type), 0, (interface.devnode.major, interface.devnode.minor)
        )
        for interface in ptr_interfaces[: topology.num_interfaces]
    ]
    ptr_pads = cast(topology.ptr_pads, POINTER(raw.media_v2_pad))
    pads = [Pad(pad.id, pad.entity_id, raw.PadFlag(pad.flags), pad.index) for pad in ptr_pads[: topology.num_pads]]
    ptr_links = cast(topology.ptr_links, POINTER(raw.media_v2_link))
    links = [
        Link(link.id, link.source_id, link.sink_id, raw.LinkFlag(link.flags))
        for link in ptr_links[: topology.num_links]
    ]

    return Topology(
        version=topology.topology_version,
        entities=entities,
        interfaces=interfaces,
        pads=pads,
        links=links,
    )


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
        info.media_version,
        info.hw_revision,
        info.driver_version,
    )


def get_raw_device_info(fd):
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


class Device(BaseDevice):
    PREFIX = "/dev/media"

    def get_topology(self):
        return get_topology(self)

    def get_device_info(self):
        return get_device_info(self)


def iter_media_files(path: PathLike = "/dev") -> Iterable[Path]:
    """Returns an iterator over all media files"""
    return iter_device_files(path=path, pattern="media*")


def iter_devices(path: PathLike = "/dev", **kwargs) -> Iterable[Device]:
    """Returns an iterator over all media devices"""
    return (Device(name, **kwargs) for name in iter_media_files(path=path))


find = make_find(iter_devices)
