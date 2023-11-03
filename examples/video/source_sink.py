#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import logging
import subprocess

from linuxpy.video.device import Device, VideoCapture, VideoOutput


def main():
    fmt = "%(threadName)-10s %(asctime)-15s %(levelname)-5s %(name)s: %(message)s"
    logging.basicConfig(level="INFO", format=fmt)

    source_dev = Device.from_id(0)
    sink_dev = Device.from_id(10)

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


try:
    main()
except KeyboardInterrupt:
    logging.info("Ctrl-C pressed. Bailing out")
