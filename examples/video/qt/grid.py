import argparse
import logging

from qtpy import QtWidgets

from linuxpy.video.device import Device
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

    COLUMNS, ROWS = 6, 3
    qcameras = set()
    for row in range(ROWS):
        for column in range(COLUMNS):
            dev_id = column + row * COLUMNS
            if dev_id > 15:
                break
            dev_id += 10
            device = Device.from_id(dev_id)
            device.open()
            qcamera = QCamera(device)
            widget = QVideoWidget(qcamera)
            layout.addWidget(widget, row, column)
            qcameras.add(qcamera)

    d0 = Device.from_id(0)
    d0.open()
    qcamera = QCamera(d0)
    qcameras.add(qcamera)
    widget = QVideoWidget(qcamera)
    layout.addWidget(widget)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
