#
# This file is part of the python-linux project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import cv2
from PyQt6 import QtCore, QtGui, QtWidgets

from linux.media.video.device import Device, VideoCapture, ControlType


class QVideo(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(QtCore.QSize(320, 240))
        self.frame = None

    def sizeHint(self):
        return QtCore.QSize(640, 480)

    def setFrame(self, frame):
        self.frame = frame
        self.image = None
        self.update()

    def paintEvent(self, _):
        frame = self.frame
        if frame is None:
            return
        if self.image is None:
            bgr = cv2.imdecode(frame.array, cv2.IMREAD_UNCHANGED)
            self.image = QtGui.QImage(
                bgr, frame.width, frame.height, QtGui.QImage.Format.Format_BGR888
            )
        painter = QtGui.QPainter(self)
        painter.drawImage(QtCore.QPointF(), self.image)



class QControlPanel(QtWidgets.QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Controls", parent)
        self.start = QtWidgets.QPushButton(">")
        self.stop = QtWidgets.QPushButton("[]")
        layout = QtWidgets.QHBoxLayout()
        self.setLayout(layout)
        layout.addWidget(self.start)
        layout.addWidget(self.stop)


def controls(device):

    for control in device.controls.values():
        if control.type in (ControlType.INTEGER, ControlType.INTEGER64, ControlType.U8, ControlType.U16, ControlType.U32):
            QtWidgets.QSpinBox()


class QCamera(QtWidgets.QWidget):
    def __init__(self, device, parent=None):
        super().__init__(parent)
        self.device = device
        controls(device)
        self.capture = VideoCapture(self.device)
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        self.video = QVideo()
        layout.addWidget(self.video)
        self.controls = QControlPanel()
        layout.addWidget(self.controls)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.next_frame)
        self.controls.start.clicked.connect(self.start)
        self.controls.stop.clicked.connect(self.stop)
        layout.setStretch(0, 1)
        layout.setStretch(1, 0)

    def next_frame(self):
        frame = next(self.stream)
        self.video.setFrame(frame)

    def start(self):
        self.stream = iter(self.device)
        self.timer.start()

    def stop(self):
        self.timer.stop()
        self.stream = None


app = QtWidgets.QApplication([])

with Device.from_id(0) as device:
    window = QCamera(device)
    window.show()
    window.capture.set_format(640, 480, "MJPG")
    app.exec()
