import pytest
from test_video import VIVID_CAPTURE_DEVICE, check_frame, vivid_only

try:
    from linuxpy.video import qt
except Exception:
    qt = None

from linuxpy.video.device import Capability, Device, PixelFormat, VideoCapture

qt_only = pytest.mark.skipif(qt is None, reason="qt not properly installed")
pytestmark = [qt_only, vivid_only]


def test_qcamera_with_vivid(qtbot, qapp):
    def check_cannot(action, state):
        with pytest.raises(RuntimeError) as error:
            getattr(qcamera, action)()
        assert error.value.args[0] == f"Cannot {action} when camera is {state}"

    with Device(VIVID_CAPTURE_DEVICE) as capture_dev:
        capture_dev.set_input(0)
        width, height, pixel_format = 640, 480, PixelFormat.RGB24
        capture = VideoCapture(capture_dev)
        capture.set_format(width, height, pixel_format)
        capture.set_fps(30)

        qcamera = qt.QCamera(capture_dev)
        assert qcamera.state() == "stopped"

        check_cannot("pause", "stopped")
        check_cannot("resume", "stopped")
        check_cannot("stop", "stopped")

        with qtbot.waitSignal(qcamera.frameChanged, timeout=100) as frames:
            with qtbot.waitSignal(qcamera.stateChanged, timeout=10) as status:
                qcamera.start()
            assert status.args[0] == "running"
            assert qcamera.state() == "running"
            check_cannot("start", "running")
            check_cannot("resume", "running")
        check_frame(frames.args[0], width, height, pixel_format, Capability.STREAMING)

        with qtbot.waitSignal(qcamera.stateChanged, timeout=10) as status:
            qcamera.pause()
        assert status.args[0] == "paused"
        assert qcamera.state() == "paused"
        check_cannot("start", "paused")
        check_cannot("pause", "paused")

        with qtbot.waitSignal(qcamera.frameChanged, timeout=100) as frames:
            with qtbot.waitSignal(qcamera.stateChanged, timeout=10) as status:
                qcamera.resume()
            assert status.args[0] == "running"
            assert qcamera.state() == "running"
            check_cannot("start", "running")
            check_cannot("resume", "running")
        check_frame(frames.args[0], width, height, pixel_format, Capability.STREAMING)

        with qtbot.waitSignal(qcamera.stateChanged, timeout=10) as status:
            qcamera.stop()
        assert status.args[0] == "stopped"
        assert qcamera.state() == "stopped"
        check_cannot("pause", "stopped")
        check_cannot("resume", "stopped")
        check_cannot("stop", "stopped")


@pytest.mark.parametrize("pixel_format", [PixelFormat.RGB24, PixelFormat.RGB32, PixelFormat.ARGB32, PixelFormat.YUYV])
def test_qvideo_widget(qtbot, pixel_format):
    with Device(VIVID_CAPTURE_DEVICE) as capture_dev:
        capture_dev.set_input(0)
        width, height = 640, 480
        capture = VideoCapture(capture_dev)
        capture.set_format(width, height, pixel_format)
        capture.set_fps(30)

        qcamera = qt.QCamera(capture_dev)
        widget = qt.QVideoWidget()
        with qtbot.waitExposed(widget):
            widget.show()
        qtbot.addWidget(widget)
        play_button = widget.controls.play_control.button
        pause_button = widget.controls.pause_control.button
        assert play_button.toolTip() == "No camera attached to this button"
        widget.set_camera(qcamera)
        assert play_button.toolTip() == "Camera is stopped. Press to start rolling"

        with qtbot.waitSignal(qcamera.frameChanged, timeout=100) as frames:
            with qtbot.waitSignal(qcamera.stateChanged, timeout=10) as status:
                play_button.click()
            assert status.args[0] == "running"
            assert qcamera.state() == "running"
        check_frame(frames.args[0], width, height, pixel_format, Capability.STREAMING)
        assert widget.video.frame is frames.args[0]
        assert play_button.toolTip() == "Camera is running. Press to stop it"

        qtbot.waitUntil(lambda: widget.video.qimage is not None)

        with qtbot.waitSignal(qcamera.stateChanged, timeout=10) as status:
            pause_button.click()
        assert status.args[0] == "paused"
        assert qcamera.state() == "paused"

        with qtbot.waitSignal(qcamera.frameChanged, timeout=100) as frames:
            with qtbot.waitSignal(qcamera.stateChanged, timeout=10) as status:
                pause_button.click()
            assert status.args[0] == "running"
            assert qcamera.state() == "running"
        check_frame(frames.args[0], width, height, pixel_format, Capability.STREAMING)

        with qtbot.waitSignal(qcamera.stateChanged, timeout=10) as status:
            play_button.click()
        assert status.args[0] == "stopped"
        assert qcamera.state() == "stopped"
