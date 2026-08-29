import argparse
import logging

from qtpy import QtWidgets

from linuxpy.video.device import iter_video_capture_devices
from linuxpy.video.qt import QCamera, QVideoWidget

try:
    import setproctitle
except ModuleNotFoundError:
    setproctitle = None


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-level", choices=["debug", "info", "warning", "error"], default="info")
    parser.add_argument("--proc-title", default="video grid")
    return parser


def main():
    args = cli().parse_args()
    fmt = "%(threadName)-10s %(asctime)-15s %(levelname)-5s %(name)s: %(message)s"
    logging.basicConfig(level=args.log_level.upper(), format=fmt)

    if setproctitle:
        setproctitle.setproctitle(args.proc_title)

    def close():
        logging.info("Stopping all cameras...")
        for qcamera in qcameras:
            qcamera.stop()
        logging.info("Done!")

    app = QtWidgets.QApplication([])
    app.aboutToQuit.connect(close)
    window = QtWidgets.QMainWindow()
    grid = QtWidgets.QWidget()
    window.setCentralWidget(grid)
    layout = QtWidgets.QGridLayout(grid)
    grid.setLayout(layout)

    devices = sorted(iter_video_capture_devices(), key=lambda d: d.index)
    n = len(devices)
    if n < 5:
        cols = 2
    elif n < 7:
        cols = 3
    elif n < 17:
        cols = 4
    else:
        cols = 5

    row, col = 0, 0
    qcameras = set()
    for device in devices:
        device.open()
        qcamera = QCamera(device)
        widget = QVideoWidget(qcamera)
        layout.addWidget(widget, row, col)
        qcameras.add(qcamera)
        if col < cols - 1:
            col += 1
        else:
            col = 0
            row += 1
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
