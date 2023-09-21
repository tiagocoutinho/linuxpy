#
# This file is part of the python-linux project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

# run from this directory with: FLASK_APP=web_ml:app flask run -h 0.0.0.0

import io
import time
from contextlib import contextmanager

import cv2
import flask
import mediapipe
import PIL
from utimer import timer

from linux.video.device import Device, PixelFormat, VideoCapture

app = flask.Flask("basic-web-cam")

mp_hands = mediapipe.solutions.hands
mp_face = mediapipe.solutions.face_mesh
mp_drawing = mediapipe.solutions.drawing_utils
mp_drawing_styles = mediapipe.solutions.drawing_styles


PREFIX = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
SUFFIX = b"\r\n"
INDEX = """\
<!doctype html>
<html lang="en">
<head>
  <link rel="icon" href="data:;base64,iVBORw0KGgo=">
</head>
<body><img src="/stream" /></body>
</html>
"""

@contextmanager
def elapsed(name) -> float:
    start = time.perf_counter()
    yield
    dt = (time.perf_counter() - start) * 1000
    print(f"{name}: {dt:.3f} ms")


def draw_hands(data, results):
    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            mp_drawing.draw_landmarks(
                data,
                hand_landmarks,
                mp_hands.HAND_CONNECTIONS,
                mp_drawing_styles.get_default_hand_landmarks_style(),
                mp_drawing_styles.get_default_hand_connections_style(),
            )


def draw_faces(data, results):
    if results.multi_face_landmarks:
        for face_landmarks in results.multi_face_landmarks:
            mp_drawing.draw_landmarks(
                image=data,
                landmark_list=face_landmarks,
                connections=mp_face.FACEMESH_TESSELATION,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_tesselation_style(),
            )
            mp_drawing.draw_landmarks(
                image=data,
                landmark_list=face_landmarks,
                connections=mp_face.FACEMESH_CONTOURS,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_contours_style(),
            )
            """
            mp_drawing.draw_landmarks(
                image=data,
                landmark_list=face_landmarks,
                connections=mp_face.FACEMESH_IRISES,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_iris_connections_style()
            )
            """
    return results


def rgb_2_jpeg(data) -> bytes:
    buff = io.BytesIO()
    PIL.Image.fromarray(data).save(buff, "jpeg")
    return buff.getvalue()


def gen_frames():
    with mp_hands.Hands(max_num_hands=1) as hands, mp_face.FaceMesh(
        max_num_faces=1
    ) as face:
        with Device.from_id(0) as device:
            capture = VideoCapture(device)
            capture.set_format(640, 480, "YUYV")
            with capture:
                for frame in capture:
                    if frame.pixel_format == PixelFormat.MJPEG:
                        bgr = cv2.imdecode(frame.array, cv2.IMREAD_UNCHANGED)
                        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                    elif frame.pixel_format == PixelFormat.YUYV:
                        data = frame.array
                        data.shape = frame.height, frame.width, -1
                        with timer["YUV 2 RGB"]:
                            rgb = cv2.cvtColor(data, cv2.COLOR_YUV2RGB_YUYV)
                    with timer["hands"]:
                        hand_results = hands.process(rgb)
                    with timer["face"]:
                        face_results = face.process(rgb)
                    draw_hands(rgb, hand_results)
                    draw_faces(rgb, face_results)
                    jpeg = rgb_2_jpeg(rgb)
                    yield b"".join((PREFIX, jpeg, SUFFIX))
                    for name, measurement in timer.measurements.items():
                        print(f"{name}: {measurement.last*1000:0.1f}ms")

@app.get("/")
def index():
    return INDEX


@app.get("/stream")
def stream():
    return flask.Response(
        gen_frames(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0")
