import argparse
import logging
import selectors

from OpenGL import GL

from linuxpy.video.device import Device, PixelFormat, VideoCapture

OPENCV_FORMATS = {
    PixelFormat.MJPEG,
    PixelFormat.YUYV,
    PixelFormat.YVYU,
    PixelFormat.UYVY,
    PixelFormat.YUV420,
    PixelFormat.NV12,
    PixelFormat.NV21,
}


def opencv_decode_frame(frame):
    import cv2

    data, fmt = frame.array, frame.pixel_format
    if fmt == PixelFormat.MJPEG:
        result = cv2.imdecode(data, cv2.IMREAD_COLOR)
    else:
        YUV_MAP = {
            PixelFormat.YUYV: cv2.COLOR_YUV2RGB_YUYV,
            PixelFormat.YVYU: cv2.COLOR_YUV2RGB_YVYU,
            PixelFormat.UYVY: cv2.COLOR_YUV2RGB_UYVY,
            PixelFormat.YUV420: cv2.COLOR_YUV2RGB_I420,
            PixelFormat.NV12: cv2.COLOR_YUV2RGB_NV12,
            PixelFormat.NV21: cv2.COLOR_YUV2RGB_NV21,
        }
        data = frame.array
        if fmt in {PixelFormat.NV12, PixelFormat.NV21, PixelFormat.YUV420}:
            data.shape = frame.height * 3 // 2, frame.width, -1
        else:
            data.shape = frame.height, frame.width, -1
        result = cv2.cvtColor(data, YUV_MAP[fmt])
    return result, GL.GL_BGR


def decode_frame(frame):
    fmt = frame.pixel_format
    if fmt == PixelFormat.RGB24:
        return frame.data, GL.GL_RGB
    elif fmt == PixelFormat.BGR24:
        return frame.data, GL.GL_BGR
    elif fmt in OPENCV_FORMATS:
        return opencv_decode_frame(frame)


def maybe_frames(capture):
    device = capture.device
    selector = selectors.DefaultSelector()
    selector.register(device, selectors.EVENT_READ)
    stream = iter(capture)
    try:
        while True:
            if selector.select(0):
                frame = next(stream)
                frame.user_data = decode_frame(frame)
                yield frame
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
    aspect = height / width
    try:
        with args.device as device:
            device.set_input(0)
            capture = VideoCapture(device, size=args.nb_buffers)
            capture.set_fps(args.frame_rate)
            capture.set_format(width, height, args.frame_format)
            fmt = capture.get_format()
            window_width = 1980
            window_height = int(window_width * aspect)
            run(capture, fmt, window_width, window_height)
    except KeyboardInterrupt:
        logging.info("Ctrl-C pressed. Bailing out")
