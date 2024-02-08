#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import argparse
import asyncio
import logging

from linuxpy.video.device import Capability, Device, PixelFormat

MODES = {
    "auto": None,
    "mmap": Capability.STREAMING,
    "read": Capability.READWRITE,
}


async def run_one(device, args):
    with device:
        async for frame in device:
            print("frame!")
            yield frame


async def run(args):
    queue = asyncio.Queue()

    async def producer(device):
        async for item in run_one(device, args):
            await queue.put((device, item))

    _ = [asyncio.create_task(producer(device)) for device in args.devices]

    while True:
        device, frame = await queue.get()
        print(f"{device.index} {frame.frame_nb}")


def device_text(text):
    try:
        return Device.from_id(int(text))
    except ValueError:
        return Device(text)


def frame_size(text):
    w, h = text.split("x", 1)
    return int(w), int(h)


def frame_format(text):
    return PixelFormat[text]


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-level", choices=["debug", "info", "warning", "error"], default="info")
    parser.add_argument("--mode", choices=MODES, default="auto")
    parser.add_argument("--nb-buffers", type=int, default=2)
    parser.add_argument("--frame-rate", type=float, default=10)
    parser.add_argument("--frame-size", type=frame_size, default="640x480")
    parser.add_argument("--frame-format", type=frame_format, default="RGB24")
    parser.add_argument("devices", type=device_text, nargs="+")
    return parser


def main(args=None):
    parser = cli()
    args = parser.parse_args(args=args)
    fmt = "%(threadName)-10s %(asctime)-15s %(levelname)-5s %(name)s: %(message)s"
    logging.basicConfig(level=args.log_level.upper(), format=fmt)

    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        logging.info("Ctrl-C pressed. Bailing out")


if __name__ == "__main__":
    main()
