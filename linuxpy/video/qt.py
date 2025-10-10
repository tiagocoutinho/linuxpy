#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

"""
Qt helpers for V4L2 (Video 4 Linux 2) subsystem.

You'll need to install linuxpy qt optional dependencies (ex: `$pip install linuxpy[qt]`)
"""

import collections
import contextlib
import logging
import select

from qtpy import QtCore, QtGui, QtWidgets

from linuxpy.video.device import (
    BaseControl,
    ControlType,
    Device,
    EventControlChange,
    EventType,
    Frame,
    PixelFormat,
    VideoCapture,
)

log = logging.getLogger(__name__)


def stream(epoll):
    while True:
        yield from epoll.poll()


@contextlib.contextmanager
def signals_blocked(widget: QtWidgets.QWidget):
    if widget.signalsBlocked():
        yield
    else:
        widget.blockSignals(True)
        try:
            yield
        finally:
            widget.blockSignals(False)


class Dispatcher:
    def __init__(self):
        self.epoll = select.epoll()
        self.cameras = {}
        self._task = None

    def ensure_task(self):
        if self._task is None:
            self._task = QtCore.QThread()
            self._task.run = self.loop
            self._task.start()
            self._task.finished.connect(self.on_quit)
        return self._task

    def on_quit(self):
        for fd in self.cameras:
            self.epoll.unregister(fd)
        self.cameras = {}

    def register(self, camera, type):
        self.ensure_task()
        fd = camera.device.fileno()
        event_mask = select.EPOLLHUP
        if type == "all" or type == "frame":
            event_mask |= select.EPOLLIN
        if type == "all" or type == "control":
            event_mask |= select.EPOLLPRI
        if fd in self.cameras:
            self.epoll.modify(fd, event_mask)
        else:
            self.epoll.register(fd, event_mask)
        self.cameras[fd] = camera

    def loop(self):
        errno = 0
        for fd, event_type in stream(self.epoll):
            camera = self.cameras[fd]
            if event_type & select.EPOLLHUP:
                print("Unregister!", fd)
                self.epoll.unregister(fd)
            else:
                if event_type & select.EPOLLPRI:
                    camera.handle_event()
                if event_type & select.EPOLLIN:
                    camera.handle_frame()
                if event_type & select.EPOLLERR:
                    errno += 1
                    print("ERROR", errno)


dispatcher = Dispatcher()


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
        dispatcher.register(self, "control")
        self.controls = {}

    def handle_frame(self):
        if self._stream is None:
            return
        frame = next(self._stream)
        self.frameChanged.emit(frame)

    def handle_event(self):
        event = self.device.deque_event()
        if event.type == EventType.CTRL:
            evt = event.u.ctrl
            if not EventControlChange.VALUE & evt.changes:
                # Skip non value changes (flags, ranges, dimensions)
                log.info("Skip event %s", event)
                return
            ctrl, controls = self.controls[event.id]
            value = None if evt.type == ControlType.BUTTON else ctrl.value
            for control in controls:
                control.valueChanged.emit(value)

    def setState(self, state):
        self._state = state
        self.stateChanged.emit(state)

    def state(self):
        return self._state

    def start(self):
        if self._state != "stopped":
            raise RuntimeError(f"Cannot start when camera is {self._state}")
        self.setState("running")
        self.capture.open()
        dispatcher.register(self, "all")
        self._stream = iter(self.capture)

    def pause(self):
        if self._state != "running":
            raise RuntimeError(f"Cannot pause when camera is {self._state}")
        dispatcher.register(self, "control")
        self.setState("paused")

    def resume(self):
        if self._state != "paused":
            raise RuntimeError(f"Cannot resume when camera is {self._state}")
        dispatcher.register(self, "all")
        self.setState("running")

    def stop(self):
        if self._state == "stopped":
            raise RuntimeError(f"Cannot stop when camera is {self._state}")
        dispatcher.register(self, "control")
        if self._stream is not None:
            self._stream.close()
            self._stream = None
        self.capture.close()
        self.setState("stopped")

    def qcontrol(self, name_or_id: str | int):
        ctrl = self.device.controls[name_or_id]
        qctrl = QControl(ctrl)
        if (info := self.controls.get(ctrl.id)) is None:
            info = ctrl, []
            self.controls[ctrl.id] = info
        info[1].append(qctrl)
        self.device.subscribe_event(EventType.CTRL, ctrl.id)
        return qctrl


class QStrValidator(QtGui.QValidator):
    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl

    def validate(self, text, pos):
        size = len(text)
        if size < self.ctrl.minimum:
            return QtGui.QValidator.State.Intermediate, text, pos
        if size > self.ctrl.maximum:
            return QtGui.QValidator.State.Invalid, text, pos
        return QtGui.QValidator.State.Acceptable, text, pos


def hbox(*widgets):
    panel = QtWidgets.QWidget()
    layout = QtWidgets.QHBoxLayout(panel)
    layout.setContentsMargins(0, 0, 0, 0)
    for widget in widgets:
        layout.addWidget(widget)
    return panel


def _reset_control(control):
    reset_button = QtWidgets.QToolButton()
    reset_button.setIcon(QtGui.QIcon.fromTheme(QtGui.QIcon.ThemeIcon.EditClear))
    reset_button.clicked.connect(control.ctrl.set_to_default)
    return reset_button


def menu_control(control):
    ctrl = control.ctrl
    combo = QtWidgets.QComboBox()
    idx_map = {}
    key_map = {}
    for idx, (key, name) in enumerate(ctrl.data.items()):
        combo.addItem(str(name), key)
        idx_map[idx] = key
        key_map[key] = idx
    combo.setCurrentIndex(key_map[ctrl.value])
    control.valueChanged.connect(lambda key: combo.setCurrentIndex(key_map[key]))
    combo.textActivated.connect(lambda txt: control.setValue(idx_map[combo.currentIndex()]))
    reset_button = _reset_control(control)
    reset_button.clicked.connect(lambda: combo.setCurrentIndex(key_map[ctrl.default]))
    return hbox(combo, reset_button)


def text_control(control):
    ctrl = control.ctrl
    line_edit = QtWidgets.QLineEdit()
    validator = QStrValidator(ctrl)
    line_edit.setValidator(validator)
    line_edit.setText(ctrl.value)
    control.valueChanged.connect(line_edit.setText)
    line_edit.editingFinished.connect(lambda: control.setValue(line_edit.text()))
    reset_button = _reset_control(control)
    reset_button.clicked.connect(lambda: line_edit.setText(ctrl.default))
    return hbox(line_edit, reset_button)


def bool_control(control):
    ctrl = control.ctrl
    widget = QtWidgets.QCheckBox()
    widget.setChecked(ctrl.value)
    control.valueChanged.connect(widget.setChecked)
    widget.clicked.connect(control.setValue)
    reset_button = _reset_control(control)
    reset_button.clicked.connect(lambda: widget.setChecked(ctrl.default))
    return hbox(widget, reset_button)


def button_control(control):
    ctrl = control.ctrl
    widget = QtWidgets.QPushButton(ctrl.name)
    widget.clicked.connect(ctrl.push)
    control.valueChanged.connect(lambda _: log.info(f"Someone clicked {ctrl.name}"))
    return widget


def integer_control(control):
    ctrl = control.ctrl
    value = ctrl.value
    slider = QtWidgets.QSlider()
    slider.setOrientation(QtCore.Qt.Orientation.Horizontal)
    slider.setRange(ctrl.minimum, ctrl.maximum)
    slider.setValue(value)
    spin = QtWidgets.QSpinBox()
    spin.setRange(ctrl.minimum, ctrl.maximum)
    spin.setValue(value)

    def on_slider_value(v):
        control.setValue(v)
        with signals_blocked(spin):
            spin.setValue(v)

    def on_spin_value(v):
        control.setValue(v)
        with signals_blocked(slider):
            slider.setValue(v)

    def on_ctrl_value(v):
        with signals_blocked(spin):
            spin.setValue(v)
        with signals_blocked(slider):
            slider.setValue(v)

    control.valueChanged.connect(on_ctrl_value)
    slider.valueChanged.connect(on_slider_value)
    spin.valueChanged.connect(on_spin_value)
    reset_button = _reset_control(control)

    def reset():
        on_ctrl_value(ctrl.default)
        ctrl.set_to_default()

    reset_button.clicked.connect(reset)
    return hbox(slider, spin, reset_button)


class QControl(QtCore.QObject):
    valueChanged = QtCore.Signal(object)

    def __init__(self, ctrl: BaseControl):
        super().__init__()
        self.ctrl = ctrl

    def setValue(self, value):
        log.info("set value %r to %s", self.ctrl.name, value)
        self.ctrl.value = value

    def create_widget(self):
        ctrl = self.ctrl
        widget = None
        if ctrl.is_flagged_has_payload and ctrl.type != ControlType.STRING:
            return
        if ctrl.type in {ControlType.INTEGER, ControlType.U8, ControlType.U16, ControlType.U32}:
            widget = integer_control(self)
        elif ctrl.type == ControlType.INTEGER64:
            pass  # TODO
        elif ctrl.type == ControlType.BOOLEAN:
            widget = bool_control(self)
        elif ctrl.type == ControlType.STRING:
            widget = text_control(self)
        elif ctrl.type in {ControlType.MENU, ControlType.INTEGER_MENU}:
            widget = menu_control(self)
        elif ctrl.type == ControlType.BUTTON:
            widget = button_control(self)
        if widget is not None:
            widget.setToolTip(ctrl.name)
            widget.setEnabled(ctrl.is_writeable)
        return widget


class QControlPanel(QtWidgets.QTabWidget):
    def __init__(self, camera: QCamera):
        super().__init__()
        self.camera = camera
        self.setWindowTitle(f"{camera.device.info.card} @ {camera.device.filename}")
        self.fill()

    def fill(self):
        camera = self.camera

        group_widgets = collections.defaultdict(list)
        for ctrl_id, ctrl in camera.device.controls.items():
            if ctrl.is_flagged_has_payload and ctrl.type != ControlType.STRING:
                continue
            qctrl = camera.qcontrol(ctrl_id)
            if (widget := qctrl.create_widget()) is None:
                continue
            if (klass := ctrl.control_class) is None:
                name = "Generic"
            else:
                name = klass.name.decode()
            group_widgets[name].append((qctrl, widget))

        for name, widgets in group_widgets.items():
            tab = QtWidgets.QWidget()
            tab.setWindowTitle(name)
            layout = QtWidgets.QGridLayout()
            tab.setLayout(layout)
            self.addTab(tab, name)
            nb_cols = 1
            nb_controls = len(widgets)
            if nb_controls > 50:
                nb_cols = 3
            elif nb_controls > 10:
                nb_cols = 2
            nb_rows = (len(widgets) + nb_cols - 1) // nb_cols
            for idx, (qctrl, widget) in enumerate(widgets):
                row, col = idx % nb_rows, idx // nb_rows
                if qctrl.ctrl.type == ControlType.BUTTON:
                    layout.addWidget(widget, row, col * 2, 1, 2)
                else:
                    layout.addWidget(QtWidgets.QLabel(f"{qctrl.ctrl.name}:"), row, col * 2)
                    layout.addWidget(widget, row, col * 2 + 1)
            layout.setRowStretch(row + 1, 1)


def fill_info_panel(camera: QCamera, widget):
    device = camera.device
    info = device.info
    layout = QtWidgets.QFormLayout(widget)
    layout.addRow("Device:", QtWidgets.QLabel(str(device.filename)))
    layout.addRow("Card:", QtWidgets.QLabel(info.card))
    layout.addRow("Driver:", QtWidgets.QLabel(info.driver))
    layout.addRow("Bus:", QtWidgets.QLabel(info.bus_info))
    layout.addRow("Version:", QtWidgets.QLabel(info.version))


def frame_sizes(camera: QCamera):
    result = set()
    for frame_size in camera.device.info.frame_types:
        result.add((frame_size.width, frame_size.height))
    return sorted(result)


def fill_inputs_panel(camera: QCamera, widget):
    device = camera.device
    info = device.info
    layout = QtWidgets.QFormLayout(widget)
    inputs_combo = QtWidgets.QComboBox()
    for inp in info.inputs:
        inputs_combo.addItem(inp.name, inp.index)
    inputs_combo.currentIndexChanged.connect(lambda: device.set_input(inputs_combo.currentData()))
    layout.addRow("Input:", inputs_combo)
    frame_size_combo = QtWidgets.QComboBox()
    for width, height in frame_sizes(camera):
        frame_size_combo.addItem(f"{width}x{height}")
    layout.addRow("Frame Size:", frame_size_combo)


class QSettingsPanel(QtWidgets.QWidget):
    def __init__(self, camera: QCamera):
        super().__init__()
        self.camera = camera
        self.fill()

    def fill(self):
        layout = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QGroupBox("General Information")
        fill_info_panel(self.camera, info)
        layout.addWidget(info)
        if self.camera.device.info.inputs:
            inputs = QtWidgets.QGroupBox("Input Settings")
            fill_inputs_panel(self.camera, inputs)
            layout.addWidget(inputs)


def to_qpixelformat(pixel_format: PixelFormat) -> QtGui.QPixelFormat | None:
    if pixel_format == PixelFormat.YUYV:
        return QtGui.qPixelFormatYuv(QtGui.QPixelFormat.YUVLayout.YUYV)


def frame_to_qimage(frame: Frame) -> QtGui.QImage:
    """Translates a Frame to a QImage"""
    data = frame.data
    if frame.pixel_format == PixelFormat.MJPEG:
        return QtGui.QImage.fromData(data, "JPG")
    fmt = QtGui.QImage.Format.Format_BGR888
    if frame.pixel_format == PixelFormat.RGB24:
        fmt = QtGui.QImage.Format.Format_RGB888
    elif frame.pixel_format == PixelFormat.RGB32:
        fmt = QtGui.QImage.Format.Format_RGB32
    elif frame.pixel_format == PixelFormat.ARGB32:
        fmt = QtGui.QImage.Format.Format_ARGB32
    elif frame.pixel_format == PixelFormat.GREY:
        fmt = QtGui.QImage.Format.Format_Grayscale8
    elif frame.pixel_format == PixelFormat.YUYV:
        import cv2

        data = frame.array
        data.shape = frame.height, frame.width, -1
        data = cv2.cvtColor(data, cv2.COLOR_YUV2BGR_YUYV)
    else:
        return None
    qimage = QtGui.QImage(data, frame.width, frame.height, fmt)
    if fmt not in {QtGui.QImage.Format.Format_RGB32}:
        qimage.convertTo(QtGui.QImage.Format.Format_RGB32)
    return qimage


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


def draw_no_image_rect(painter, rect, line_width=4):
    color = QtGui.QColor(255, 0, 0, 100)
    pen = QtGui.QPen(color, line_width)
    painter.setPen(pen)
    painter.setBrush(QtCore.Qt.NoBrush)
    painter.drawLines(
        (
            QtCore.QLineF(rect.topLeft(), rect.bottomRight()),
            QtCore.QLineF(rect.bottomLeft(), rect.topRight()),
        )
    )
    half_line_width = line_width // 2
    rect.setLeft(rect.left() + half_line_width)
    rect.setRight(rect.right() - half_line_width)
    rect.setTop(rect.top() + half_line_width)
    rect.setBottom(rect.bottom() - half_line_width)
    painter.drawRect(rect)


def draw_no_image(painter, width, height, line_width=4):
    rect = QtCore.QRectF(0, 0, width, height)
    return draw_no_image_rect(painter, rect, line_width)


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
    qimage = None

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
        self.qimage = None
        self.update()

    def paintEvent(self, _):
        frame = self.frame
        painter = QtGui.QPainter(self)
        if frame is None:
            draw_no_image(painter, self.width(), self.height())
            return
        if self.qimage is None:
            self.qimage = frame_to_qimage(frame)
        if self.qimage is not None:
            width, height = self.width(), self.height()
            scaled_image = self.qimage.scaled(width, height, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
            pix_width, pix_height = scaled_image.width(), scaled_image.height()
            x, y = 0, 0
            if width > pix_width:
                x = int((width - pix_width) / 2)
            if height > pix_height:
                y = int((height - pix_height) / 2)
            painter.drawImage(QtCore.QPoint(x, y), scaled_image)

    def minimumSizeHint(self):
        return QtCore.QSize(160, 120)


class QVideoItem(QtWidgets.QGraphicsObject):
    frame = None
    qimage = None
    imageChanged = QtCore.Signal(object)

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
        self.qimage = None
        self.update()

    def boundingRect(self):
        if self.frame:
            width = self.frame.width
            height = self.frame.height
        elif self.camera:
            fmt = self.camera.capture.get_format()
            width = fmt.width
            height = fmt.height
        else:
            width = 640
            height = 480
        return QtCore.QRectF(0.0, 0.0, width, height)

    def paint(self, painter, style, *args):
        frame = self.frame
        rect = self.boundingRect()
        if frame is None:
            draw_no_image_rect(painter, rect)
            return
        changed = self.qimage is None
        if changed:
            self.qimage = frame_to_qimage(frame)
        painter.drawImage(rect, self.qimage)
        if changed:
            self.imageChanged.emit(self.qimage)


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

    def stop():
        if camera.state() != "stopped":
            camera.stop()

    parser = argparse.ArgumentParser()
    parser.add_argument("--log-level", choices=["debug", "info", "warning", "error"], default="info")
    parser.add_argument("device", type=int)
    args = parser.parse_args()
    fmt = "%(threadName)-10s %(asctime)-15s %(levelname)-5s %(name)s: %(message)s"
    logging.basicConfig(level=args.log_level.upper(), format=fmt)
    app = QtWidgets.QApplication([])
    with Device.from_id(args.device, blocking=False) as device:
        camera = QCamera(device)
        window = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(window)
        widget = QVideoWidget(camera)
        widget.setMinimumSize(640, 480)
        panel = QControlPanel(camera)
        settings = QSettingsPanel(camera)
        layout.addWidget(settings)
        layout.addWidget(widget)
        layout.addWidget(panel)
        window.show()
        app.aboutToQuit.connect(stop)
        app.exec()


if __name__ == "__main__":
    main()
