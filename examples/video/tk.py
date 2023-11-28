#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import argparse
import logging
from io import BytesIO
from tkinter import READABLE, Canvas, Tk

from PIL import Image, ImageTk

from linuxpy.video.device import Capability, Device, VideoCapture


def device_text(text):
    try:
        return Device.from_id(int(text))
    except ValueError:
        return Device(text)


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-level", choices=["debug", "info", "warning", "error"], default="info")
    parser.add_argument("-s", "--source", choices=["auto", "stream", "read"], default="auto")
    parser.add_argument("device", type=device_text)
    return parser


def run(device, source):
    def update(cam, mask=None):
        cam.image = frame()  # don't loose reference
        canvas.itemconfig(container, image=cam.image)

    def frame():
        frame = next(stream)
        buff = BytesIO(bytes(frame))
        image = Image.open(buff, formats=["JPEG"])
        return ImageTk.PhotoImage(image)

    with device as cam:
        video_capture = VideoCapture(cam, source=source)
        fmt = video_capture.get_format()
        video_capture.set_format(fmt.width, fmt.height, "MJPG")
        with video_capture as buffers:
            stream = iter(buffers)
            window = Tk()
            window.title("Join")
            window.geometry(f"{fmt.width}x{fmt.height}")
            window.configure(background="grey")
            canvas = Canvas(window, width=fmt.width, height=fmt.height)
            canvas.pack(side="bottom", fill="both", expand="yes")
            container = canvas.create_image(0, 0, anchor="nw")
            window.tk.createfilehandler(cam, READABLE, update)
            window.mainloop()


def main(args=None):
    parser = cli()
    args = parser.parse_args(args=args)
    fmt = "%(threadName)-10s %(asctime)-15s %(levelname)-5s %(name)s: %(message)s"
    logging.basicConfig(level=args.log_level.upper(), format=fmt)

    if args.source == "auto":
        source = None
    elif args.source == "stream":
        source = Capability.STREAMING
    elif args.source == "read":
        source = Capability.READWRITE

    try:
        run(args.device, source)
    except KeyboardInterrupt:
        logging.info("Ctrl-C pressed. Bailing out")


if __name__ == "__main__":
    main()
