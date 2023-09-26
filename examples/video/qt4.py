#
# This file is part of the python-linux project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import cv2
from PyQt6 import QtCore, QtGui, QtWidgets

from linuxpy.video.device import Device, VideoCapture


def update():
    frame = next(stream)
    bgr = cv2.imdecode(frame.array, cv2.IMREAD_UNCHANGED)
    img = QtGui.QImage(
        bgr, frame.width, frame.height, QtGui.QImage.Format.Format_BGR888
    )
    item.setPixmap(QtGui.QPixmap.fromImage(img))


app = QtWidgets.QApplication([])
view = QtWidgets.QGraphicsView()
scene = QtWidgets.QGraphicsScene()
item = QtWidgets.QGraphicsPixmapItem()
scene.addItem(item)
view.setScene(scene)
view.show()

timer = QtCore.QTimer()
timer.timeout.connect(update)

with Device.from_id(0) as cam:
    capture = VideoCapture(cam)
    capture.set_format(1280, 720, "MJPG")
    stream = iter(cam)
    timer.start(30)
    app.exec()
