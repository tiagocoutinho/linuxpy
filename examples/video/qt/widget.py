#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

# install extra requirements:
# python3 -m pip install opencv-python qtpy pyqt6

# run from this directory with:
# QT_API=pyqt6 python widget.py

import argparse
import logging

import cv2
from qtpy import QtCore, QtGui, QtWidgets

from linuxpy.video.device import Device, MemoryMap, PixelFormat, ReadSource, VideoCapture

MODES = {
    "auto": None,
    "mmap": MemoryMap,
    "read": ReadSource,
}


def frame_to_qimage(frame):
    data = frame.array
    fmt = QtGui.QImage.Format.Format_BGR888
    if frame.pixel_format == PixelFormat.MJPEG:
        img = QtGui.QImage()
        img.loadFromData(frame.data)
        return img
    elif frame.pixel_format == PixelFormat.YUYV:
        data.shape = frame.height, frame.width, -1
        data = cv2.cvtColor(data, cv2.COLOR_YUV2BGR_YUYV)
    elif frame.pixel_format == PixelFormat.RGB24:
        fmt = QtGui.QImage.Format.Format_RGB888
    elif frame.pixel_format == PixelFormat.RGB32:
        fmt = QtGui.QImage.Format.Format_RGB32
    elif frame.pixel_format == PixelFormat.ARGB32:
        fmt = QtGui.QImage.Format.Format_ARGB32
    return QtGui.QImage(data, frame.width, frame.height, fmt)


def frame_to_qpixmap(frame):
    qimage = frame_to_qimage(frame)
    return QtGui.QPixmap.fromImage(qimage)


def draw_frame(painter, width, height, line_width=4, color="red"):
    half_line_width = line_width // 2
    pen = QtGui.QPen(QtGui.QColor(color), line_width)
    painter.setPen(pen)
    painter.setBrush(QtCore.Qt.NoBrush)
    painter.drawRect(half_line_width, half_line_width, width - line_width, height - line_width)


def draw_no_frame(painter, width, height, line_width=4):
    color = QtGui.QColor(255, 0, 0, 100)
    pen = QtGui.QPen(color, line_width)
    painter.setPen(pen)
    painter.setBrush(QtCore.Qt.NoBrush)
    painter.drawLines(
        (
            QtCore.QLine(0, height, width, 0),
            QtCore.QLine(0, 0, width, height),
        )
    )
    draw_frame(painter, width, height, line_width, color)


class QVideo(QtWidgets.QWidget):
    frame = None
    image = None

    def setFrame(self, frame):
        self.frame = frame
        self.pixmap = None
        self.update()

    def paintEvent(self, _):
        frame = self.frame
        painter = QtGui.QPainter(self)
        width, height = self.width(), self.height()
        if frame is None:
            draw_no_frame(painter, width, height)
            return
        if self.pixmap is None:
            self.pixmap = frame_to_qpixmap(frame)
        if self.pixmap is not None:
            scaled_pixmap = self.pixmap.scaled(width, height, QtCore.Qt.AspectRatioMode.KeepAspectRatio)

            pix_width, pix_height = scaled_pixmap.width(), scaled_pixmap.height()
            x, y = 0, 0
            if width > pix_width:
                x = int((width - pix_width) / 2)
            if height > pix_height:
                y = int((height - pix_height) / 2)
            painter.drawPixmap(QtCore.QPoint(x, y), scaled_pixmap)
            draw_frame(painter, width, height, 4)

    def minimumSizeHint(self):
        return QtCore.QSize(160, 120)


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


def main():
    args = cli().parse_args()
    device = args.device
    width, height = args.frame_size

    fmt = "%(threadName)-10s %(asctime)-15s %(levelname)-5s %(name)s: %(message)s"
    logging.basicConfig(level=args.log_level.upper(), format=fmt)

    def update():
        frame = next(stream)
        window.setFrame(frame)

    app = QtWidgets.QApplication([])
    window = QVideo()
    window.show()

    timer = QtCore.QTimer()
    timer.timeout.connect(update)

    with device:
        capture = VideoCapture(device, buffer_type=MODES[args.mode], size=args.nb_buffers)
        capture.set_fps(args.frame_rate)
        capture.set_format(width, height, args.frame_format)
        with capture:
            stream = iter(capture)
            timer.start(0)
            app.exec()


if __name__ == "__main__":
    main()
