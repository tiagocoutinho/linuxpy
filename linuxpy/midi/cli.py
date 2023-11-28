#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import argparse
import asyncio

from linuxpy.midi.device import (
    EVENT_TYPE_INFO,
    EventType,
    PortCapability,
    PortType,
    Sequencer,
    iter_read_clients,
    iter_read_ports,
    struct_text,
)


def event_text(event):
    data = EVENT_TYPE_INFO.get(event.type)
    if data is None:
        return event.type.name
    name, member_name = data
    result = f"{event.client_id:>3}:{event.port_id:<3} {name:<20} "
    if event.type == EventType.SYSEX:
        result += " ".join(f"{i:02X}" for i in event.raw_data)
    elif event.type == EventType.CLOCK:
        queue_ctrl = event.queue_ctrl
        real_time = queue_ctrl.param.time.time
        timestamp = real_time.tv_sec + real_time.tv_nsec * 1e-9
        result += f"queue={queue_ctrl.queue} {timestamp=}"
    elif member_name:
        member = getattr(event.event.data, member_name)
        result += struct_text(member)
    return result


def listen(seq, args):
    for addr in args.addr:
        port = seq.create_port(f"listen on {addr}")
        port.connect_from(addr)
    for event in seq:
        print(event_text(event))


async def async_listen(seq, args):
    for addr in args.addr:
        port = seq.create_port(f"listen on {addr}")
        port.connect_from(addr)
    async for event in seq:
        print(event_text(event))


def iter_all_ports(seq):
    for client in iter_read_clients(seq):
        yield from iter_read_ports(seq, client.client)


def ls(seq, _):
    print(f"{'Port':^7} {'Client':<24} {'Port':<24} {'Type':<30} {'Capabilities'}")
    for client in iter_read_clients(seq):
        cname = client.name.decode()
        for port in iter_read_ports(seq, client.client):
            pname = port.name.decode()
            capability = PortCapability(port.capability)
            caps = str(capability).split(".", 1)[-1]
            caps = caps.replace("SUBS_", "S").replace("READ", "R").replace("WRITE", "W").replace("|", ", ")
            ptype = str(PortType(port.type)).split(".", 1)[-1].replace("|", ", ")
            print(f"{port.addr.client:3}:{port.addr.port:<3} {cname:<24} {pname:<24} {ptype:<30} {caps}")


def cli(seq):
    ports = {(port.addr.client, port.addr.port) for port in iter_all_ports(seq)}

    def address(text):
        client, port = text.split(":", 1)
        addr = int(client), int(port)
        if addr not in ports:
            raise ValueError(f"Port {text} not found")
        return addr

    parser = argparse.ArgumentParser()
    sub_parsers = parser.add_subparsers(
        title="sub-commands", description="valid sub-commands", help="select one command", required=True, dest="command"
    )
    listen = sub_parsers.add_parser("listen", aliases=["dump"], help="listen for events on selected port(s)")
    listen.add_argument("addr", help="address(es)", type=address, nargs="+")
    alisten = sub_parsers.add_parser("alisten", aliases=["adump"], help="listen for events on selected port(s)")
    alisten.add_argument("addr", help="address(es)", type=address, nargs="+")
    sub_parsers.add_parser("ls", help="list clients and ports")
    return parser


def run(seq, args):
    if args.command in {"listen", "dump"}:
        listen(seq, args)
    elif args.command in {"alisten", "adump"}:
        asyncio.run(async_listen(seq, args))
    elif args.command == "ls":
        ls(seq, args)


def main(args=None):
    with Sequencer("linuxpy midi cli") as seq:
        parser = cli(seq)
        args = parser.parse_args(args=args)
        try:
            run(seq, args)
        except KeyboardInterrupt:
            print("\rCtrl-C pressed. Bailing out")


if __name__ == "__main__":
    main()
