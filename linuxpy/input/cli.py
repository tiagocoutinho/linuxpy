#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import argparse
import asyncio

from linuxpy.input.device import Bus, Device, async_event_batch_stream, event_batch_stream, find


def ls(_):
    print(f"{'Name':32} {'Bus':10} {'Location':32} {'Version':8} {'Filename':32}")
    for dev in sorted(find(find_all=True), key=lambda d: d.index):
        with dev:
            try:
                physical_location = dev.physical_location
            except OSError:
                physical_location = "-"
            did = dev.device_id
            try:
                bus = Bus(did.bustype).name
            except ValueError:
                bus = "-"
            print(f"{dev.name:<32} {bus:<10} {physical_location:<32} {dev.version:<8} {dev.filename}")


def print_event(device, event):
    print(f"{device.index:2} {device.name:32} {event.type.name:6} {event.code.name:16} {event.value}")


def listen(args):
    print(f" # {'Name':32} {'Type':6} {'Code':16} {'Value':6}")
    with Device.from_id(args.addr) as device:
        for batch in event_batch_stream(device.fileno()):
            for event in batch:
                print_event(device, event)


async def async_listen(args):
    print(f" # {'Name':32} {'Type':6} {'Code':16} {'Value':6}")
    queue = asyncio.Queue()

    async def go(addr):
        with Device.from_id(addr) as device:
            async for event in async_event_batch_stream(device.fileno()):
                await queue.put((device, event))

    _ = [asyncio.create_task(go(addr)) for addr in args.addr]

    while True:
        device, batch = await queue.get()
        for event in batch:
            print_event(device, event)


def cli():
    parser = argparse.ArgumentParser()
    sub_parsers = parser.add_subparsers(
        title="sub-commands", description="valid sub-commands", help="select one command", required=True, dest="command"
    )
    listen = sub_parsers.add_parser("listen", aliases=["dump"], help="listen for events on selected input")
    listen.add_argument("addr", help="address", type=int)
    alisten = sub_parsers.add_parser("alisten", aliases=["adump"], help="listen for events on selected input(s)")
    alisten.add_argument("addr", help="address(es)", type=int, nargs="+")
    sub_parsers.add_parser("ls", help="list inputs")
    return parser


def run(args):
    if args.command in {"listen", "dump"}:
        listen(args)
    elif args.command in {"alisten", "adump"}:
        asyncio.run(async_listen(args))
    elif args.command == "ls":
        ls(args)


def main(args=None):
    parser = cli()
    args = parser.parse_args(args=args)
    try:
        run(args)
    except KeyboardInterrupt:
        print("\rCtrl-C pressed. Bailing out")


if __name__ == "__main__":
    main()
