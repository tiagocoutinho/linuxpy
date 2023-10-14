#
# This file is part of the python-linux project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import logging
from io import BytesIO
from tkinter import READABLE, Canvas, Tk
from sys import argv

from PIL import Image, ImageTk

from linuxpy.video.device import Device, VideoCapture, Capability

fmt = "%(threadName)-10s %(asctime)-15s %(levelname)-5s %(name)s: %(message)s"
logging.basicConfig(level="INFO", format=fmt)


def frame():
    frame = next(stream)
    buff = BytesIO(bytes(frame))
    image = Image.open(buff, formats=["JPEG"])
    return ImageTk.PhotoImage(image)


def update(cam, mask=None):
    cam.image = frame()  # don't loose reference
    canvas.itemconfig(container, image=cam.image)


import argparse
parser = argparse.ArgumentParser("v4l2-tk")
parser.add_argument("-d", "--device", type=int, default=0)
parser.add_argument("-s", "--source", choices=["auto", "stream", "read"], default="auto")
args = parser.parse_args()
if args.source == "auto":
    source = None
elif args.source == "stream":
    source = Capability.STREAMING
elif args.source == "read":
    source = Capability.READWRITE

with Device.from_id(args.device) as cam:
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
