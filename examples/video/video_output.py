#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import itertools
import logging
import subprocess
import time

import numpy

from linuxpy.video.device import Device, PixelFormat, VideoOutput


def main():
    fmt = "%(threadName)-10s %(asctime)-15s %(levelname)-5s %(name)s: %(message)s"
    logging.basicConfig(level="INFO", format=fmt)

    device = Device.from_id(10)
    width, height = (640, 480)
    N = 24

    frames = tuple(numpy.random.randint(0, high=256, size=(height, width, 3), dtype=numpy.uint8) for _ in range(N))

    with device:
        sink = VideoOutput(device)
        sink.set_format(width, height, PixelFormat.RGB24)
        with sink:
            proc = subprocess.Popen(["cvlc", f"v4l2://{device.filename}"])
            try:
                for i in itertools.count():
                    sink.write(frames[i % N].data)
                    time.sleep(0.1)
            finally:
                proc.terminate()


try:
    main()
except KeyboardInterrupt:
    logging.info("Ctrl-C pressed. Bailing out")
