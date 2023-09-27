#
# This file is part of the python-linux project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import cv2
from qtpy import QtCore, QtGui, QtWidgets

from linuxpy.video.device import Device, VideoCapture


def update():
    frame = next(stream)
    bgr = cv2.imdecode(frame.array, cv2.IMREAD_UNCHANGED)
    img = QtGui.QImage(bgr, 640, 480, QtGui.QImage.Format.Format_BGR888)
    label.setPixmap(QtGui.QPixmap.fromImage(img))
    # app.processEvents()


app = QtWidgets.QApplication([])
window = QtWidgets.QMainWindow()
label = QtWidgets.QLabel()
window.setCentralWidget(label)
window.show()

timer = QtCore.QTimer()
timer.timeout.connect(update)

with Device.from_id(0) as cam:
    capture = VideoCapture(cam)
    capture.set_format(640, 480, "MJPG")
    stream = iter(cam)
    timer.start(0)
    app.exec()
