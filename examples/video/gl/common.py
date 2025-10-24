import argparse
import logging
import selectors

from linuxpy.video.device import Device, PixelFormat, VideoCapture


class RGFWWindow:
    def __init__(self, name, x, y, width, height, flags=None):
        import RGFW

        self.lib = RGFW
        self.name = name
        self.rect = RGFW.rect(x, y, width, height)
        self.flags = RGFW.CENTER if flags is None else flags
        self.win = None

    def create(self):
        self.win = self.lib.createWindow(self.name, self.rect, self.flags)

    def swapBuffers(self):
        self.win.swapBuffers()

    def handle_events(self):
        lib = self.lib
        win = self.win
        while win.checkEvent():
            if win.event.type == lib.quit or lib.isPressed(win, lib.Escape):
                return False
        return True

    def __enter__(self):
        self.create()
        return self

    def __exit__(self, *args):
        self.win.close()
        self.win = None


def maybe_frames(capture):
    device = capture.device
    selector = selectors.DefaultSelector()
    selector.register(device, selectors.EVENT_READ)
    stream = iter(capture)
    try:
        while True:
            if selector.select(0):
                yield next(stream)
            else:
                yield None
    finally:
        selector.unregister(device)


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
    parser.add_argument("--nb-buffers", type=int, default=2)
    parser.add_argument("--frame-rate", type=float, default=10)
    parser.add_argument("--frame-size", type=frame_size, default="640x480")
    parser.add_argument("--frame-format", type=frame_format, default="RGB24")
    parser.add_argument("device", type=device_text)
    return parser


def main(run, args=None):
    parser = cli()
    args = parser.parse_args(args=args)
    fmt = "%(threadName)-10s %(asctime)-15s %(levelname)-5s %(name)s: %(message)s"
    logging.basicConfig(level=args.log_level.upper(), format=fmt)
    width, height = args.frame_size
    try:
        with args.device as device:
            device.set_input(0)
            capture = VideoCapture(device, size=args.nb_buffers)
            capture.set_fps(args.frame_rate)
            capture.set_format(width, height, args.frame_format)
            run(capture)
    except KeyboardInterrupt:
        logging.info("Ctrl-C pressed. Bailing out")
