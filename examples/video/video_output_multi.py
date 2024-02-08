#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import argparse
import concurrent.futures
import itertools
import logging
import time

import numpy
import yaml

try:
    import setproctitle
except ModuleNotFoundError:
    setproctitle = None

from linuxpy.video.device import Device, PixelFormat, VideoOutput

STOP = False


def device_text(text):
    try:
        return Device.from_id(int(text))
    except ValueError:
        return Device(text)


def frame_size(text):
    w, h = text.split("x", 1)
    return int(w), int(h)


def run(device_config):
    device = device_text(device_config["name"])
    frame_rate = device_config.get("frame_rate", 1)
    width, height = frame_size(device_config.get("frame_size", "640x480"))
    fmt = PixelFormat[device_config.get("frame_format", "ARGB32").upper()]
    N = min(100, max(10, int(frame_rate // 2)))
    logging.info("Preparing %d frames...", N)
    depth = 3 if fmt == PixelFormat.RGB24 else 4
    frames = tuple(numpy.random.randint(0, high=256, size=(height, width, depth), dtype=numpy.uint8) for _ in range(N))
    with device:
        sink = VideoOutput(device)
        sink.set_format(width, height, fmt)
        sink.set_fps(frame_rate)
        with sink:
            start = time.monotonic()
            last, last_n, skipped = 0, 0, 0
            for i in itertools.count():
                if STOP:
                    print(f"STOPPING {device}....")
                    return
                frame_n = i + 1
                sink.write(frames[i % N])
                next = start + (frame_n / frame_rate)
                now = time.monotonic()
                if now - last > 0.5:
                    elapsed = now - last
                    n = frame_n - last_n
                    rate = n / elapsed
                    print(
                        f"Frame: {i:>8} | Elapsed: {now-start:>8.1f} s | Rate: {rate:>8.1f} fps | Skipped: {skipped:>8}"
                    )
                    last = now
                    last_n = frame_n
                if now < next:
                    time.sleep(next - now)
                else:
                    skipped += 1


def safe_run(device_config):
    try:
        run(device_config)
    except Exception:
        logging.exception("Failed to run")


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-level", choices=["debug", "info", "warning", "error"], default="info")
    parser.add_argument("--config", default="video_output_multi.yml")
    parser.add_argument("--proc-title", default="video_output_multi")
    return parser


def main(args=None):
    global STOP
    parser = cli()
    args = parser.parse_args(args=args)
    fmt = "%(threadName)-10s %(asctime)-15s %(levelname)-5s %(name)s: %(message)s"
    logging.basicConfig(level=args.log_level.upper(), format=fmt)

    if setproctitle:
        setproctitle.setproctitle(args.proc_title)

    with open(args.config) as fobj:
        config = yaml.load(fobj, yaml.UnsafeLoader)

    devices = config["devices"]
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(devices)) as executor:
            _ = {executor.submit(safe_run, device) for device in devices}
    except KeyboardInterrupt:
        STOP = True
        logging.info("Ctrl-C pressed. Bailing out")


if __name__ == "__main__":
    main()
