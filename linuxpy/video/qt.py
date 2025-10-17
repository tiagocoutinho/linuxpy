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
    BufferType,
    ControlType,
    Device,
    EventControlChange,
    EventType,
    Frame,
    FrameSizeType,
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
        self._stream = iter(self.capture)
        dispatcher.register(self, "all")

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


class QVideoStream(QtCore.QObject):
    qimage = None
    imageChanged = QtCore.Signal(object)

    def __init__(self, camera: QCamera | None = None):
        super().__init__()
        self.camera = None
        self.set_camera(camera)

    def on_frame(self, frame):
        self.frame = frame
        self.qimage = frame_to_qimage(frame)
        self.imageChanged.emit(self.qimage)

    def set_camera(self, camera: QCamera | None = None):
        if self.camera:
            self.camera.frameChanged.disconnect(self.on_frame)
        self.camera = camera
        if self.camera:
            self.camera.frameChanged.connect(self.on_frame)


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


def control_group_widget(widgets):
    group = QtWidgets.QWidget()
    layout = QtWidgets.QFormLayout(group)
    for qctrl, widget in widgets:
        if qctrl.ctrl.type == ControlType.BUTTON:
            layout.addWidget(widget)
        else:
            layout.addRow(f"{qctrl.ctrl.name}:", widget)
    return group


def control_widgets(camera):
    widgets = collections.defaultdict(list)
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
        widgets[name].append((qctrl, widget))
    return widgets


class QControlPanel(QtWidgets.QTabWidget):
    def __init__(self, camera: QCamera):
        super().__init__()
        self.camera = camera
        self.setWindowTitle(f"{camera.device.info.card} @ {camera.device.filename}")
        self.fill()

    def fill(self):
        group_widgets = control_widgets(self.camera)
        for name, widgets in group_widgets.items():
            area = QtWidgets.QScrollArea()
            tab = control_group_widget(widgets)
            area.setWidget(tab)
            self.addTab(area, name)


def fill_info_panel(camera: QCamera, widget):
    device = camera.device
    info = device.info
    layout = QtWidgets.QFormLayout(widget)
    layout.addRow("Device:", QtWidgets.QLabel(str(device.filename)))
    layout.addRow("Card:", QtWidgets.QLabel(info.card))
    layout.addRow("Driver:", QtWidgets.QLabel(info.driver))
    layout.addRow("Bus:", QtWidgets.QLabel(info.bus_info))
    layout.addRow("Version:", QtWidgets.QLabel(info.version))


def fill_inputs_panel(camera: QCamera, widget):
    def on_camera_state(state):
        stopped = state == "stopped"
        inputs_combo.setEnabled(stopped)
        sizes_combo.setEnabled(stopped)
        width_spin.setEnabled(stopped)
        height_spin.setEnabled(stopped)
        fps_combo.setEnabled(stopped)
        pixfmt_combo.setEnabled(stopped)

    def on_input(index):
        if index < 0:
            return
        device.set_input(inputs_combo.currentData())
        update_sizes()
        update_fps()
        update_formats()

    def on_frame_size(_):
        fmt = device.get_format(BufferType.VIDEO_CAPTURE)
        if sizes_combo.isEnabled():
            if sizes_combo.currentIndex() < 0:
                return
            width, height = sizes_combo.currentData()
        else:
            width, height = width_spin.value(), height_spin.value()
        device.set_format(BufferType.VIDEO_CAPTURE, width, height, fmt.pixel_format)
        update_fps()

    def on_fps(index):
        if index < 0:
            return
        device.set_fps(BufferType.VIDEO_CAPTURE, fps_combo.currentData())

    def on_format(index):
        if index < 0:
            return
        curr_fmt = device.get_format(BufferType.VIDEO_CAPTURE)
        pixel_format = pixfmt_combo.currentData()
        device.set_format(BufferType.VIDEO_CAPTURE, curr_fmt.width, curr_fmt.height, pixel_format)
        update_fps()

    def update_input():
        curr_input = device.get_input()
        inputs_combo.clear()
        for inp in info.inputs:
            inputs_combo.addItem(inp.name, inp.index)
        inputs_combo.setCurrentIndex(curr_input)

    def update_formats():
        curr_fmt = capture.get_format()
        formats = info.buffer_formats(BufferType.VIDEO_CAPTURE)
        pixfmt_combo.clear()
        for fmt in sorted(formats, key=lambda fmt: fmt.pixel_format.name):
            pixfmt_combo.addItem(fmt.pixel_format.name, fmt.pixel_format)
        pixfmt_combo.setCurrentText(curr_fmt.pixel_format.name)

    def update_sizes():
        curr_fmt = capture.get_format()
        sizes = info.format_frame_sizes(curr_fmt.pixel_format)
        continuous = len(sizes) == 1 and sizes[0].type != FrameSizeType.DISCRETE
        if continuous:
            size = sizes[0]
            width_spin.setRange(size.info.min_width, size.info.max_width)
            width_spin.setSingleStep(size.info.step_width)
            width_spin.setValue(curr_fmt.width)
            height_spin.setRange(size.info.min_height, size.info.max_height)
            height_spin.setSingleStep(size.info.step_height)
            height_spin.setValue(curr_fmt.height)
        else:
            sizes_combo.clear()
            sizes = {(size.info.width, size.info.height) for size in sizes}
            for size in sorted(sizes):
                width, height = size
                sizes_combo.addItem(f"{width}x{height}", (width, height))
            sizes_combo.setCurrentText(f"{curr_fmt.width}x{curr_fmt.height}")
        layout.setRowVisible(width_spin, continuous)
        layout.setRowVisible(height_spin, continuous)
        layout.setRowVisible(sizes_combo, not continuous)

    def update_fps():
        curr_fmt = capture.get_format()
        opts = info.fps_intervals(curr_fmt.pixel_format, curr_fmt.width, curr_fmt.height)
        opts = (opt.min_fps for opt in opts if opt.min_fps == opt.max_fps)
        curr_fps = capture.get_fps()
        fps_combo.clear()
        for fps in sorted(opts):
            fps_combo.addItem(str(fps), fps)
        fps_combo.setCurrentText(str(curr_fps))

    camera.stateChanged.connect(on_camera_state)

    device = camera.device
    capture = camera.capture
    info = device.info

    layout = QtWidgets.QFormLayout(widget)
    inputs_combo = QtWidgets.QComboBox()
    layout.addRow("Input:", inputs_combo)
    inputs_combo.currentIndexChanged.connect(on_input)

    sizes_combo = QtWidgets.QComboBox()
    sizes_combo.currentTextChanged.connect(on_frame_size)
    layout.addRow("Size:", sizes_combo)
    width_spin = QtWidgets.QSpinBox()
    height_spin = QtWidgets.QSpinBox()
    layout.addRow("Width:", width_spin)
    layout.addRow("Height:", height_spin)
    width_spin.valueChanged.connect(on_frame_size)
    height_spin.valueChanged.connect(on_frame_size)

    fps_combo = QtWidgets.QComboBox()
    fps_combo.currentIndexChanged.connect(on_fps)
    layout.addRow("FPS:", fps_combo)

    pixfmt_combo = QtWidgets.QComboBox()
    layout.addRow("Format:", pixfmt_combo)
    pixfmt_combo.currentIndexChanged.connect(on_format)

    update_input()
    update_sizes()
    update_fps()
    update_formats()


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


FORMAT_MAP = {
    PixelFormat.RGB24: QtGui.QImage.Format.Format_RGB888,
    PixelFormat.RGB32: QtGui.QImage.Format.Format_RGB32,
    PixelFormat.RGBA32: QtGui.QImage.Format.Format_RGBA8888,
    PixelFormat.ARGB32: QtGui.QImage.Format.Format_ARGB32,
    PixelFormat.XRGB32: QtGui.QImage.Format.Format_ARGB32,
    PixelFormat.GREY: QtGui.QImage.Format.Format_Grayscale8,
}


def frame_to_qimage(frame: Frame) -> QtGui.QImage | None:
    """Translates a Frame to a QImage"""
    data = frame.data
    if frame.pixel_format == PixelFormat.MJPEG:
        return QtGui.QImage.fromData(data, "JPG")
    elif frame.pixel_format == PixelFormat.YUYV:
        import cv2

        data = frame.array
        data.shape = frame.height, frame.width, -1
        data = cv2.cvtColor(data, cv2.COLOR_YUV2BGR_YUYV)
        fmt = QtGui.QImage.Format.Format_RGB888
    else:
        if (fmt := FORMAT_MAP.get(frame.pixel_format)) is None:
            return None
    return QtGui.QImage(data, frame.width, frame.height, fmt)


def frame_to_qpixmap(frame: Frame) -> QtGui.QPixmap:
    if frame.pixel_format == PixelFormat.MJPEG:
        pixmap = QtGui.QPixmap(frame.width, frame.height)
        pixmap.loadFromData(frame.data, "JPG")
        return pixmap
    qimage = frame_to_qimage(frame)
    return QtGui.QPixmap.fromImage(qimage)


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


def draw_frame(widget, frame): ...


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


def paint_image(painter, width, height, qimage=None):
    if qimage is None:
        draw_no_image(painter, width, height)
        return
    image_width = qimage.width()
    image_height = qimage.height()
    scale = min(width / image_width, height / image_height)
    rect_width = int(image_width * scale)
    rect_height = int(image_height * scale)
    x = int((width - rect_width) / 2)
    y = int((height - rect_height) / 2)
    rect = QtCore.QRect(x, y, rect_width, rect_height)
    painter.drawImage(rect, qimage)


class VideoMixin:
    qimage = None

    def imageRect(self):
        return self.rect()

    def paint(self, painter, _, *args):
        rect = self.imageRect()
        paint_image(painter, rect.width(), rect.height(), self.qimage)

    def on_image_changed(self, qimage):
        self.qimage = qimage
        self.update()


class QVideo(VideoMixin, QtWidgets.QWidget):
    def paintEvent(self, _):
        self.paint(QtGui.QPainter(self), None)

    def minimumSizeHint(self):
        return QtCore.QSize(160, 120)


class QVideoItem(VideoMixin, QtWidgets.QGraphicsItem):
    def boundingRect(self):
        width, height = 640, 480
        if self.qimage:
            width, height = self.qimage.width(), self.qimage.height()
        return QtCore.QRectF(0, 0, width, height)

    imageRect = boundingRect


class QVideoWidget(QtWidgets.QWidget):
    def __init__(self, camera=None):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        self.video = QVideo()
        self.stream = QVideoStream(camera)
        self.stream.imageChanged.connect(self.video.on_image_changed)
        self.controls = QVideoControls(camera)
        layout.addWidget(self.video)
        layout.addWidget(self.controls)
        layout.setStretchFactor(self.video, 1)

    def set_camera(self, camera: QCamera | None = None):
        self.stream.set_camera(camera)
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
        video = QVideoWidget(camera)
        panel = QControlPanel(camera)
        settings = QSettingsPanel(camera)
        layout.addWidget(settings)
        layout.addWidget(video)
        layout.addWidget(panel)
        layout.setStretchFactor(video, 1)
        window.show()
        app.aboutToQuit.connect(stop)
        app.exec()


if __name__ == "__main__":
    main()
