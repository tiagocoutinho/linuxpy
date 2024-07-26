#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

"""
Qt helpers for V4L2 (Video 4 Linux 2) subsystem.

You'll need to install linuxpy qt optional dependencies (ex: `$pip install linuxpy[qt]`)
"""

import logging

from qtpy import QtCore, QtGui, QtWidgets

from linuxpy.video.device import Device, Frame, PixelFormat, VideoCapture


class QCamera(QtCore.QObject):
    frameChanged = QtCore.Signal(object)
    stateChanged = QtCore.Signal(str)

    def __init__(self, device: Device):
        super().__init__()
        self.device = device
        self.capture = VideoCapture(device)
        self._stop = False
        self._stream = None
        self._state = "stopped"

    def on_frame(self):
        frame = next(self._stream)
        self.frameChanged.emit(frame)

    def setState(self, state):
        self._state = state
        self.stateChanged.emit(state)

    def state(self):
        return self._state

    def start(self):
        if self._state != "stopped":
            return
        self.setState("running")
        self.device.open()
        self.capture.open()
        self._stream = iter(self.capture)
        self._notifier = QtCore.QSocketNotifier(self.device.fileno(), QtCore.QSocketNotifier.Type.Read)
        self._notifier.activated.connect(self.on_frame)

    def pause(self):
        if self._state != "running":
            return
        self._notifier.setEnabled(False)
        self.setState("paused")

    def resume(self):
        if self._state != "paused":
            return
        self._notifier.setEnabled(True)
        self.setState("running")

    def stop(self):
        self._notifier.setEnabled(False)
        self._stream.close()
        self.capture.close()
        self.device.close()
        self._notifier = None
        self.setState("stopped")


def to_qpixelformat(pixel_format: PixelFormat) -> QtGui.QPixelFormat | None:
    if pixel_format == PixelFormat.YUYV:
        return QtGui.qPixelFormatYuv(QtGui.QPixelFormat.YUVLayout.YUYV)


def frame_to_qimage(frame: Frame) -> QtGui.QImage:
    """Translates a Frame to a QImage"""
    if frame.pixel_format == PixelFormat.MJPEG:
        return QtGui.QImage.fromData(frame.data, b"JPG")
    fmt = QtGui.QImage.Format.Format_BGR888
    if frame.pixel_format == PixelFormat.RGB24:
        fmt = QtGui.QImage.Format.Format_RGB888
    elif frame.pixel_format == PixelFormat.RGB32:
        fmt = QtGui.QImage.Format.Format_RGB32
    elif frame.pixel_format == PixelFormat.ARGB32:
        fmt = QtGui.QImage.Format.Format_ARGB32
    elif frame.pixel_format == PixelFormat.YUYV:
        import cv2

        data = frame.array
        data.shape = frame.height, frame.width, -1
        data = cv2.cvtColor(data, cv2.COLOR_YUV2BGR_YUYV)
    return QtGui.QImage(frame.data, frame.width, frame.height, fmt)


def frame_to_qpixmap(frame: Frame) -> QtGui.QPixmap:
    if frame.pixel_format == PixelFormat.MJPEG:
        pixmap = QtGui.QPixmap(frame.width, frame.height)
        pixmap.loadFromData(frame.data, b"JPG")
        return pixmap
    qimage = frame_to_qimage(frame)
    return QtGui.QPixmap.fromImage(qimage)


def draw_frame(paint_device, width, height, line_width=4, color="red"):
    if width is None:
        width = paint_device.width()
    if height is None:
        height = paint_device.height()
    half_line_width = line_width // 2
    pen = QtGui.QPen(QtGui.QColor(color), line_width)
    painter = QtGui.QPainter(paint_device)
    painter.setPen(pen)
    painter.setBrush(QtCore.Qt.NoBrush)
    painter.drawRect(half_line_width, half_line_width, width - line_width, height - line_width)


def draw_no_image(paint_device, width=None, height=None, line_width=4):
    if width is None:
        width = paint_device.width()
    if height is None:
        height = paint_device.height()
    color = QtGui.QColor(255, 0, 0, 100)
    pen = QtGui.QPen(color, line_width)
    painter = QtGui.QPainter(paint_device)
    painter.setPen(pen)
    painter.setBrush(QtCore.Qt.NoBrush)
    painter.drawLines(
        (
            QtCore.QLine(0, height, width, 0),
            QtCore.QLine(0, 0, width, height),
        )
    )
    half_line_width = line_width // 2
    painter.drawRect(half_line_width, half_line_width, width - line_width, height - line_width)


class QVideoInfo(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self._init()

    def _init(self):
        layout = QtWidgets.QFormLayout()
        self.setLayout(layout)


class BaseCameraControl:
    def __init__(self, camera: QCamera | None = None):
        self.camera = None
        self.set_camera(camera)

    def set_camera(self, camera: QCamera | None):
        if self.camera:
            self.camera.stateChanged.disconnect(self.on_camera_state_changed)
        self.camera = camera
        if self.camera:
            self.camera.stateChanged.connect(self.on_camera_state_changed)
            state = self.camera.state()
        else:
            state = None
        self.on_camera_state_changed(state)

    def on_camera_state_changed(self, state):
        pass


class PlayButtonControl(BaseCameraControl):
    play_icon = "media-playback-start"
    stop_icon = "media-playback-stop"

    def __init__(self, button, camera: QCamera | None = None):
        self.button = button
        self.button.clicked.connect(self.on_click)
        super().__init__(camera)

    def on_camera_state_changed(self, state):
        enabled = True
        icon = self.stop_icon
        if state is None:
            enabled = False
            tip = "No camera attached to this button"
        elif state == "stopped":
            icon = self.play_icon
            tip = "Camera is stopped. Press to start rolling"
        else:
            tip = f"Camera is {state}. Press to stop it"
        self.button.setEnabled(enabled)
        self.button.setIcon(QtGui.QIcon.fromTheme(icon))
        self.button.setToolTip(tip)

    def on_click(self):
        if self.camera:
            if self.camera.state() == "stopped":
                self.camera.start()
            else:
                self.camera.stop()


class PauseButtonControl(BaseCameraControl):
    play_icon = "media-playback-start"
    pause_icon = "media-playback-pause"

    def __init__(self, button, camera: QCamera | None = None):
        self.button = button
        self.button.clicked.connect(self.on_click)
        super().__init__(camera)

    def on_camera_state_changed(self, state):
        if state is None:
            tip = "No camera attached to this button"
        elif state == "stopped":
            tip = "Camera is stopped"
        elif state == "paused":
            tip = "Camera is paused. Press to resume"
        else:
            tip = f"Camera is {state}. Press to pause"
        enabled = state not in {None, "stopped"}
        icon = self.play_icon if state == "paused" else self.pause_icon
        self.button.setEnabled(enabled)
        self.button.setIcon(QtGui.QIcon.fromTheme(icon))
        self.button.setToolTip(tip)

    def on_click(self):
        if self.camera is None:
            return
        if self.camera.state() == "running":
            self.camera.pause()
        else:
            self.camera.resume()


class StateControl(BaseCameraControl):
    def __init__(self, label, camera: QCamera | None = None):
        self.label = label
        super().__init__(camera)

    def on_camera_state_changed(self, state):
        if state is None:
            state = "---"
        self.label.setText(state)


class QVideoControls(QtWidgets.QWidget):
    def __init__(self, camera: QCamera | None = None):
        super().__init__()
        self.camera = None
        self._init()
        self.set_camera(camera)

    def _init(self):
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        state_label = QtWidgets.QLabel("")
        play_button = QtWidgets.QToolButton()
        pause_button = QtWidgets.QToolButton()
        self.camera_label = QtWidgets.QLabel("")
        layout.addWidget(self.camera_label)
        layout.addStretch(1)
        layout.addWidget(state_label)
        layout.addWidget(play_button)
        layout.addWidget(pause_button)
        self.state_control = StateControl(state_label)
        self.play_control = PlayButtonControl(play_button)
        self.pause_control = PauseButtonControl(pause_button)

    def set_camera(self, camera: QCamera | None = None):
        self.state_control.set_camera(camera)
        self.play_control.set_camera(camera)
        self.pause_control.set_camera(camera)
        if camera is None:
            name = "---"
        else:
            name = camera.device.filename.stem
        self.camera_label.setText(name)
        self.camera = camera


class QVideo(QtWidgets.QWidget):
    frame = None
    image = None

    def __init__(self, camera: QCamera | None = None):
        super().__init__()
        self.camera = None
        self.set_camera(camera)

    def set_camera(self, camera: QCamera | None = None):
        if self.camera:
            self.camera.frameChanged.disconnect(self.on_frame_changed)
        self.camera = camera
        if self.camera:
            self.camera.frameChanged.connect(self.on_frame_changed)

    def on_frame_changed(self, frame):
        self.frame = frame
        self.pixmap = None
        self.update()

    def paintEvent(self, _):
        frame = self.frame
        if frame is None:
            draw_no_image(self)
            return
        if self.pixmap is None:
            self.pixmap = frame_to_qpixmap(frame)
        if self.pixmap is not None:
            width, height = self.width(), self.height()
            scaled_pixmap = self.pixmap.scaled(width, height, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
            pix_width, pix_height = scaled_pixmap.width(), scaled_pixmap.height()
            x, y = 0, 0
            if width > pix_width:
                x = int((width - pix_width) / 2)
            if height > pix_height:
                y = int((height - pix_height) / 2)
            painter = QtGui.QPainter(self)
            painter.drawPixmap(QtCore.QPoint(x, y), scaled_pixmap)

    def minimumSizeHint(self):
        return QtCore.QSize(160, 120)


class QVideoWidget(QtWidgets.QWidget):
    def __init__(self, camera=None):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        self.video = QVideo(camera)
        self.controls = QVideoControls(camera)
        layout.addWidget(self.video)
        layout.addWidget(self.controls)
        layout.setStretchFactor(self.video, 1)

    def set_camera(self, camera: QCamera | None = None):
        self.video.set_camera(camera)
        self.controls.set_camera(camera)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--log-level", choices=["debug", "info", "warning", "error"], default="info")
    parser.add_argument("device", type=int)
    args = parser.parse_args()
    fmt = "%(threadName)-10s %(asctime)-15s %(levelname)-5s %(name)s: %(message)s"
    logging.basicConfig(level=args.log_level.upper(), format=fmt)
    app = QtWidgets.QApplication([])
    device = Device.from_id(args.device)
    camera = QCamera(device)
    widget = QVideoWidget(camera)
    app.aboutToQuit.connect(camera.stop)
    widget.show()
    app.exec()


if __name__ == "__main__":
    main()
