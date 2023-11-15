#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import argparse
import asyncio

from linuxpy.midi.device import (
    PortCapability,
    Sequencer,
    async_event_stream,
    event_stream,
    iter_read_clients,
    iter_read_ports,
)


def address(text):
    client, port = text.split(":", 1)
    return int(client), int(port)


def listen(seq, args):
    for addr in args.addr:
        port = seq.create_port(f"listen on {addr}")
        port.connect_from(*addr)
    for event in event_stream(seq):
        print(event)


async def async_listen(seq, args):
    for addr in args.addr:
        port = seq.create_port(f"listen on {addr}")
        port.connect_from(*addr)
    async for event in async_event_stream(seq):
        print(event)


def ls(seq, _):
    for client in iter_read_clients(seq):
        cname = client.name.decode()
        for port in iter_read_ports(seq, client.client):
            pname = port.name.decode()
            caps = repr(PortCapability(port.capability))
            caps = caps.removeprefix("<PortCapability.").rsplit(":", 1)[0]
            print(f" {port.addr.client:3}:{port.addr.port}  {cname:<24}  {pname:<24}  {caps}")


def cli(args=None):
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
    parser = cli(args)
    args = parser.parse_args(args=args)
    with Sequencer("linuxpy midi cli") as seq:
        try:
            run(seq, args)
        except KeyboardInterrupt:
            print("\rCtrl-C pressed. Bailing out")


if __name__ == "__main__":
    main()
