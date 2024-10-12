# linuxpy

[![linuxpy][pypi-version]](https://pypi.python.org/pypi/linuxpy)
[![Python Versions][pypi-python-versions]](https://pypi.python.org/pypi/linuxpy)
![License][license]
[![CI][CI]](https://github.com/tiagocoutinho/linuxpy/actions/workflows/ci.yml)

[![Source][source]](https://github.com/tiagocoutinho/linuxpy/)
[![Documentation][documentation]](https://tiagocoutinho.github.io/linuxpy/)

Human friendly interface to linux subsystems using python.

Provides python access to several linux subsystems like V4L2, GPIO, Led, thermal,
input and MIDI.

There is experimental, undocumented, incomplete and unstable access to USB.

Requirements:
* python >= 3.9
* Fairly recent linux kernel
* Installed kernel modules you want to access

And yes, it is true: there are no python libraries required! Also there are no
C libraries required. Everything is done here through direct ioctl, read and
write calls. Ain't linux wonderful?

## Installation

From within your favorite python environment:

```console
$ pip install linuxpy
```

To run the examples you'll need:

```console
$ pip install linuxpy[examples]
```

To develop, run tests, build package, lint, etc you'll need:

```console
$ pip install linuxpy[dev]
```

## Subsystems

### Video

Video for Linux 2 (V4L2) python library

Without further ado:

```python
>>> from linuxpy.video.device import Device
>>> with Device.from_id(0) as cam:
>>>     for i, frame in enumerate(cam):
...         print(f"frame #{i}: {len(frame)} bytes")
...         if i > 9:
...             break
...
frame #0: 54630 bytes
frame #1: 50184 bytes
frame #2: 44054 bytes
frame #3: 42822 bytes
frame #4: 42116 bytes
frame #5: 41868 bytes
frame #6: 41322 bytes
frame #7: 40896 bytes
frame #8: 40844 bytes
frame #9: 40714 bytes
frame #10: 40662 bytes
```

Getting information about the device:

```python
>>> from linuxpy.video.device import Device, BufferType

>>> cam = Device.from_id(0)
>>> cam.open()
>>> cam.info.card
'Integrated_Webcam_HD: Integrate'

>>> cam.info.capabilities
<Capability.STREAMING|EXT_PIX_FORMAT|VIDEO_CAPTURE: 69206017>

>>> cam.info.formats
[ImageFormat(type=<BufferType.VIDEO_CAPTURE: 1>, description=b'Motion-JPEG',
             flags=<ImageFormatFlag.COMPRESSED: 1>, pixelformat=<PixelFormat.MJPEG: 1196444237>),
 ImageFormat(type=<BufferType.VIDEO_CAPTURE: 1>, description=b'YUYV 4:2:2',
             flags=<ImageFormatFlag.0: 0>, pixelformat=<PixelFormat.YUYV: 1448695129>)]

>>> cam.get_format(BufferType.VIDEO_CAPTURE)
Format(width=640, height=480, pixelformat=<PixelFormat.MJPEG: 1196444237>}

>>> for ctrl in cam.controls.values(): print(ctrl)
<IntegerControl brightness min=0 max=255 step=1 default=128 value=128>
<IntegerControl contrast min=0 max=255 step=1 default=32 value=32>
...
<BooleanControl exposure_dynamic_framerate default=False value=False>

>>> cam.controls.brightness
<IntegerControl brightness min=0 max=255 step=1 default=128 value=128>
>>> cam.controls.brightness.value = 64
>>> cam.controls.brightness
<IntegerControl brightness min=0 max=255 step=1 default=128 value=64>
```

(see also [v4l2py-ctl](examples/video/v4l2py-ctl.py) example)

#### asyncio

linuxpy.video is asyncio friendly:

```console
$ python -m asyncio

>>> from linuxpy.video.device import Device
>>> with Device.from_id(0) as camera:
...     async for frame in camera:
...         print(f"frame {len(frame)}")
frame 10224
frame 10304
frame 10224
frame 10136
...
```

(check [basic async](examples/video/basic_async.py) and [web async](examples/video/web/async.py) examples)

#### gevent

linuxpy.video is also gevent friendly:

```
$ python

>>> from linuxpy.io import GeventIO
>>> from linuxpy.video.device import Device
>>> with Device.from_id(0, io=GeventIO) as camera:
...     for frame in camera:
...         print(f"frame {len(frame)}")
frame 10224
frame 10304
frame 10224
frame 10136
...
```

(check [basic gevent](examples/basic_gevent.py) and [web gevent](examples/web/sync.py) examples)

#### Video output

It is possible to write to a video output capable device (ex: v4l2loopback).
The following example shows how to grab frames from device 0 and write them
to device 10

```console
>>> from linuxpy.video.device import Device, VideoOutput, BufferType
>>> dev_source = Device.from_id(0)
>>> dev_sink = Device.from_id(10)
>>> with dev_source, dev_target:
>>>     source = VideoCapture(dev_source)
>>>     sink = VideoOutput(dev_sink)
>>>     source.set_format(640, 480, "MJPG")
>>>     sink.set_format(640, 480, "MJPG")
>>>     with source, sink:
>>>         for frame in source:
>>>             sink.write(frame.data)
```

#### Bonus track

You've been patient enough to read until here so, just for you,
a 20 line gem: a flask web server displaying your device on the web:

```console
$ pip install flask
```

```python
# web.py

import flask
from linuxpy.video.device import Device

app = flask.Flask('basic-web-cam')

def gen_frames():
    with Device.from_id(0) as cam:
        for frame in cam:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame.data + b"\r\n"

@app.route("/")
def index():
    return '<html><img src="/stream" /></html>'

@app.route("/stream")
def stream():
    return flask.Response(
        gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
```

run with:

```console
$ FLASK_APP=web flask run -h 0.0.0.0
```

Point your browser to [127.0.0.1:5000](http://127.0.0.1:5000) and you should see
your camera rolling!

#### v4l2loopback

Start from scratch:
```console
# Remove kernel module and all devices (no client can be connected at this point)
sudo modprobe -r v4l2loopback

# Install some devices
sudo modprobe v4l2loopback video_nr=20,21 card_label="Loopback 0","Loopback 1"
```

#### References

See the ``linux/videodev2.h`` header file for details.


* [V4L2 (Latest)](https://www.kernel.org/doc/html/latest/userspace-api/media/v4l/v4l2.html) ([videodev.h](https://www.kernel.org/doc/html/latest/userspace-api/media/v4l/videodev.html))
* [V4L2 6.2](https://www.kernel.org/doc/html/v6.2/userspace-api/media/v4l/v4l2.html) ([videodev.h](https://www.kernel.org/doc/html/v6.2/userspace-api/media/v4l/videodev.html))


### Input

API not documented yet. Just this example:

```python
import time
from linuxpy.input.device import find_gamepads

pad = next(find_gamepads())
abs = pad.absolute

with pad:
    while True:
	    print(f"X:{abs.x:>3} | Y:{abs.y:>3} | RX:{abs.rx:>3} | RY:{abs.ry:>3}", end="\r", flush=True)
	    time.sleep(0.1)
```

#### asyncio

```console
$ python -m asyncio

>>> from linuxpy.input.device import find_gamepads
>>> with next(find_gamepads()) as pad:
...     async for event in pad:
...         print(event)
InputEvent(time=1697520475.348099, type=<EventType.SYN: 0>, code=<Synchronization.REPORT: 0>, value=0)
InputEvent(time=1697520475.361564, type=<EventType.REL: 2>, code=<Relative.X: 0>, value=-1)
InputEvent(time=1697520475.361564, type=<EventType.REL: 2>, code=<Relative.Y: 1>, value=1)
InputEvent(time=1697520475.361564, type=<EventType.SYN: 0>, code=<Synchronization.REPORT: 0>, value=0)
InputEvent(time=1697520475.371128, type=<EventType.REL: 2>, code=<Relative.X: 0>, value=-1)
InputEvent(time=1697520475.371128, type=<EventType.SYN: 0>, code=<Synchronization.REPORT: 0>, value=0)
...
```

#### References

* [Input (Latest)](https://www.kernel.org/doc/html/latest/input/)
* [Input 6.2](https://www.kernel.org/doc/html/v6.2/input/)

### MIDI Sequencer

```console
$ python

>>> from linuxpy.midi.device import Sequencer, event_stream

>>> seq = Sequencer()
>>> with seq:
        port = seq.create_port()
        port.connect_from(14, 0)
        for event in seq:
            print(event)
 14:0   Note on              channel=0, note=100, velocity=3, off_velocity=0, duration=0
 14:0   Clock                queue=0, pad=b''
 14:0   System exclusive     F0 61 62 63 F7
 14:0   Note off             channel=0, note=55, velocity=3, off_velocity=0, duration=0
```

#### asyncio

asyncio is a first class citizen to linuxpy.midi:

```console
$ python -m asyncio

>>> from linuxpy.midi.device import Sequencer, async_event_stream

>>> seq = Sequencer()
>>> with seq:
        port = seq.create_port()
        port.connect_from(14, 0)
        async for event in async_event_stream(seq):
            print(event)
 14:0   Note on              channel=0, note=100, velocity=3, off_velocity=0, duration=0
 14:0   Clock                queue=0, pad=b''
 14:0   System exclusive     F0 61 62 63 F7
 14:0   Note off             channel=0, note=55, velocity=3, off_velocity=0, duration=0
```

#### CLI

A basic CLI is provided that allows listing MIDI clients & ports
and dumping MIDI sequencer events:

```console
$ python -m linuxpy.midi.cli ls
 Port   Client                   Port                     Type                           Capabilities
  0:0   System                   Timer                    0                              SR, W, R
  0:1   System                   Announce                 0                              SR, R
 14:0   Midi Through             Midi Through Port-0      PORT, SOFTWARE, MIDI_GENERIC   SW, SR, W, R
```

```console
$ python -m linuxpy.midi.cli listen 0:1 14:0
  0:1   Port subscribed      sender=(client=0, port=1), dest=(client=128, port=0)
  0:1   Port start           client=128, port=1
  0:1   Port subscribed      sender=(client=14, port=0), dest=(client=128, port=1)
  0:1   Client start         client=130, port=0
  0:1   Port start           client=130, port=0
  0:1   Port subscribed      sender=(client=130, port=0), dest=(client=14, port=0)
 14:0   Note on              channel=0, note=100, velocity=3, off_velocity=0, duration=0
  0:1   Port unsubscribed    sender=(client=130, port=0), dest=(client=14, port=0)
  0:1   Port exit            client=130, port=0
  0:1   Client exit          client=130, port=0
  0:1   Port exit            client=129, port=0
  0:1   Client exit          client=129, port=0
  0:1   Client start         client=129, port=0
  0:1   Port start           client=129, port=0
 14:0   Note on              channel=0, note=100, velocity=3, off_velocity=0, duration=0
 14:0   Note on              channel=0, note=0, velocity=255, off_velocity=0, duration=0
 14:0   Note on              channel=0, note=0, velocity=255, off_velocity=0, duration=0
```

[pypi-python-versions]: https://img.shields.io/pypi/pyversions/linuxpy.svg
[pypi-version]: https://img.shields.io/pypi/v/linuxpy.svg
[pypi-status]: https://img.shields.io/pypi/status/linuxpy.svg
[license]: https://img.shields.io/pypi/l/linuxpy.svg
[CI]: https://github.com/tiagocoutinho/linuxpy/actions/workflows/ci.yml/badge.svg
[documentation]: https://img.shields.io/badge/Documentation-blue?color=grey&logo=mdBook
[source]: https://img.shields.io/badge/Source-grey?logo=git
