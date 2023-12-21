#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import argparse
import logging
import time

from linuxpy.video.device import Capability, Device, PixelFormat, VideoCapture

MODES = {
    "auto": None,
    "mmap": Capability.STREAMING,
    "read": Capability.READWRITE,
}


def run(args):
    device = args.device
    width, height = args.frame_size

    with device:
        capture = VideoCapture(device, source=MODES[args.mode], size=args.nb_buffers)
        capture.set_fps(args.frame_rate)
        capture.set_format(width, height, args.frame_format)
        start = last = time.monotonic()
        last_update = 0
        with capture:
            fmt = capture.get_format()
            fps = capture.get_fps()
            device.log.info(f"Starting capture {fmt.width}x{fmt.height} at {fps} fps in {fmt.pixel_format.name}")
            for frame in capture:
                new = time.monotonic()
                fps, last = 1 / (new - last), new
                if new - last_update > 0.5:
                    elapsed = new - start
                    size = len(frame) / 1000
                    print(
                        f"Frame: {frame.frame_nb:>8} Size: {size:>8.1f} Kb | Elapsed: {elapsed:>8.1f} s | Rate {fps:>8.1f} fps",
                        end="\r",
                    )
                    last_update = new


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
    parser.add_argument("device", type=device_text)
    return parser


def main(args=None):
    parser = cli()
    args = parser.parse_args(args=args)
    fmt = "%(threadName)-10s %(asctime)-15s %(levelname)-5s %(name)s: %(message)s"
    logging.basicConfig(level=args.log_level.upper(), format=fmt)

    try:
        run(args)
    except KeyboardInterrupt:
        logging.info("Ctrl-C pressed. Bailing out")


if __name__ == "__main__":
    main()
