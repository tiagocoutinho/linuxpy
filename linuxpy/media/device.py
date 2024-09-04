#
# This file is part of the linuxpy project
#
# Copyright (c) 2024 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import collections
import errno

from linuxpy.ctypes import POINTER, cast, cvoidp
from linuxpy.device import BaseDevice
from linuxpy.ioctl import ioctl

from . import raw

Entity = collections.namedtuple("Entity", "id name type flags")
EntityDesc = collections.namedtuple("EntityDesc", "id name type flags pads outbound_links devnode")
Interface = collections.namedtuple("Interface", "id type flags devnode")
Pad = collections.namedtuple("Pad", "id entity_id flags index")
Link = collections.namedtuple("Link", "id source_id sink_id flags")
Topology = collections.namedtuple("Topology", "version entities interfaces pads links")
DeviceInfo = collections.namedtuple(
    "DeviceInfo", "driver model serial bus_info media_version hw_revision driver_version"
)


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
    raw_entity_desc = raw.media_entity_desc(id=raw.ENTITY_ID_FLAG_NEXT)
    for desc in iter_read(fd, raw.IOC.ENUM_ENTITIES, raw_entity_desc):
        yield EntityDesc(
            desc.id,
            desc.name.decode(),
            raw.EntityFunction(desc.type),
            raw.EntityFlag(desc.flags),
            desc.pads,
            desc.links,
            (desc.dev.major, desc.dev.minor),
        )
        raw_entity_desc.id |= raw.ENTITY_ID_FLAG_NEXT


class Device(BaseDevice):
    PREFIX = "/dev/media"

    def get_topology(self):
        return get_topology(self)

    def get_device_info(self):
        return get_device_info(self)
