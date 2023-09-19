
#
# This file is part of the python-linux project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

from contextlib import contextmanager
from time import perf_counter

import cv2
import pyqtgraph as pg
from PyQt6 import QtCore

from linux.media.video.device import Device, VideoCapture

pg.setConfigOption("imageAxisOrder", "row-major")
app = pg.mkQApp("V4L2 Qt demo")

## Create window with GraphicsView widget
win = pg.GraphicsLayoutWidget()
win.show()  ## show widget alone in its own window
win.setWindowTitle("V4L2 Qt demo")
view = win.addViewBox()

## lock the aspect ratio so pixels are always square
# view.setAspectLocked(True)
plot = pg.PlotItem()
view.addItem(plot)

## Create image item
img = pg.ImageItem(border="w")

# view.invertY(True)
plot.addItem(img)


@contextmanager
def elapsed(name) -> float:
    start = perf_counter()
    yield
    dt = (perf_counter() - start) * 1000
    print(f"{name}: {dt:.3f} ms")


def update():
    frame = next(stream)
    bgr = cv2.imdecode(frame.array, cv2.IMREAD_UNCHANGED)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    # rgb = numpy.flipud(rgb)
    img.setImage(rgb)


with Device.from_id(0) as cam:
    capture = VideoCapture(cam)
    capture.set_format(640, 480, "MJPG")
    print(capture.get_format())
    stream = iter(cam)

    timer = QtCore.QTimer()
    timer.timeout.connect(update)
    timer.start(0)

    pg.exec()
