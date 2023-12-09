#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import argparse
import itertools
import logging
import subprocess
import time

import numpy

from linuxpy.video.device import Capability, Device, PixelFormat, VideoOutput

MODES = {
    "auto": None,
    "mmap": Capability.STREAMING,
    "write": Capability.READWRITE,
}


def run(args):
    device = args.device
    frame_rate = args.frame_rate
    width, height = args.frame_size
    gui = args.gui

    N = min(100, int(frame_rate // 2))

    frames = tuple(numpy.random.randint(0, high=256, size=(height, width, 3), dtype=numpy.uint8) for _ in range(N))

    with device:
        sink = VideoOutput(device, sink=MODES[args.mode], size=args.nb_buffers)
        sink.set_format(width, height, PixelFormat.RGB24)
        with sink:
            if gui:
                proc = subprocess.Popen(["cvlc", f"v4l2://{device.filename}"])
            start = time.monotonic()
            last, last_n, skipped = 0, 0, 0
            try:
                for i in itertools.count():
                    frame_n = i + 1
                    sink.write(frames[i % N].data)
                    next = start + (frame_n / frame_rate)
                    now = time.monotonic()
                    if now - last > 0.1:
                        elapsed = now - last
                        n = frame_n - last_n
                        rate = n / elapsed
                        print(
                            f"Frame: {i:>8} | Elapsed: {elapsed:>8.1f} s | Rate: {rate:>8.1f} fps | Skipped: {skipped:>8}",
                            end="\r",
                        )
                        last = now
                        last_n = frame_n
                    if now < next:
                        time.sleep(next - now)
                    else:
                        skipped += 1
            finally:
                if gui:
                    proc.terminate()


def device_text(text):
    try:
        return Device.from_id(int(text))
    except ValueError:
        return Device(text)


def frame_size(text):
    w, h = text.split("x", 1)
    return int(w), int(h)


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-level", choices=["debug", "info", "warning", "error"], default="info")
    parser.add_argument("--frame-rate", type=float, default=10)
    parser.add_argument("--frame-size", type=frame_size, default="640x480")
    parser.add_argument("--nb-buffers", type=int, default=2)
    parser.add_argument("--mode", choices=["auto", "mmap", "write"], default="auto")
    parser.add_argument("--gui", type=bool, default=True, action=argparse.BooleanOptionalAction)
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
