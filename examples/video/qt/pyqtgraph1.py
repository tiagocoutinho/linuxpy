import contextlib
import logging

from pyqtgraph import GraphicsLayout, GraphicsView, setConfigOption
from qtpy import QtWidgets

from linuxpy.video.device import BufferType, PixelFormat, iter_video_capture_devices
from linuxpy.video.qt import QCamera, QVideoControls, QVideoItem, QVideoStream


def main():
    import argparse

    def stop():
        for camera in cameras:
            if camera.state() != "stopped":
                camera.stop()

    def update_image(image_item, frame):
        data = frame.array
        data.shape = frame.height, frame.width, -1
        image_item.setImage(data)

    parser = argparse.ArgumentParser()
    parser.add_argument("--log-level", choices=["debug", "info", "warning", "error"], default="info")
    args = parser.parse_args()

    setConfigOption("imageAxisOrder", "row-major")
    # setConfigOption('useNumba', True)
    fmt = "%(threadName)-10s %(asctime)-15s %(levelname)-5s %(name)s: %(message)s"
    logging.basicConfig(level=args.log_level.upper(), format=fmt)
    app = QtWidgets.QApplication([])
    with contextlib.ExitStack() as stack:
        idevices = iter_video_capture_devices()
        devices = sorted((stack.enter_context(dev) for dev in idevices), key=lambda dev: dev.index)
        for device in devices:
            device.set_format(BufferType.VIDEO_CAPTURE, 640, 480, PixelFormat.RGB24)
            device.set_fps(BufferType.VIDEO_CAPTURE, 15)

        cameras = [QCamera(device) for device in devices]

        window = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(window)
        video = QtWidgets.QWidget()
        video_layout = QtWidgets.QHBoxLayout(video)
        controls_panel = QtWidgets.QWidget()
        controls_layout = QtWidgets.QVBoxLayout(controls_panel)
        view = GraphicsView()
        view_layout = GraphicsLayout(border=(100, 100, 100))
        view.setCentralItem(view_layout)
        view.setViewport(QtWidgets.QOpenGLWidget())
        view.setMinimumSize(640, 480)
        video_layout.addWidget(view)

        n = len(devices)
        if n < 5:
            cols = 2
        elif n < 7:
            cols = 3
        elif n < 17:
            cols = 4
        else:
            cols = 5
        for i, camera in enumerate(cameras, start=1):
            controls = QVideoControls(camera)
            controls_layout.addWidget(controls)
            view_box = view_layout.addViewBox(name=f"Camera {camera.device.index}", lockAspect=True, invertY=True)
            # image_item = ImageItem()
            # camera.frameChanged.connect(functools.partial(update_image, image_item))
            image_item = QVideoItem()
            image_item.stream = QVideoStream(camera)
            image_item.stream.imageChanged.connect(image_item.on_image_changed)
            view_box.addItem(image_item)
            if not i % cols:
                view_layout.nextRow()

        layout.addWidget(video)
        layout.addWidget(controls_panel)
        layout.setStretch(0, 1)
        window.show()
        app.aboutToQuit.connect(stop)
        [camera.start() for camera in cameras]
        app.exec()


if __name__ == "__main__":
    main()
