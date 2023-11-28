#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import argparse
import logging
import subprocess

from linuxpy.video.device import Device, VideoCapture, VideoOutput


def run(source_dev, sink_dev):
    with source_dev, sink_dev:
        source = VideoCapture(source_dev)
        sink = VideoOutput(sink_dev)
        source.set_format(640, 480, "MJPG")
        sink.set_format(640, 480, "MJPG")
        sink.set_fps(2)
        with source, sink:
            proc = subprocess.Popen(["cvlc", f"v4l2://{sink_dev.filename}"])
            try:
                for frame in source:
                    sink.write(frame.data)
            finally:
                proc.terminate()


def device_text(text):
    try:
        return Device.from_id(int(text))
    except ValueError:
        return Device(text)


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-level", choices=["debug", "info", "warning", "error"], default="info")
    parser.add_argument("source", type=device_text)
    parser.add_argument("dest", type=device_text)
    return parser


def main(args=None):
    parser = cli()
    args = parser.parse_args(args=args)
    fmt = "%(threadName)-10s %(asctime)-15s %(levelname)-5s %(name)s: %(message)s"
    logging.basicConfig(level=args.log_level.upper(), format=fmt)

    try:
        run(args.source, args.dest)
    except KeyboardInterrupt:
        logging.info("Ctrl-C pressed. Bailing out")


if __name__ == "__main__":
    main()
