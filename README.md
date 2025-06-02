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
* python >= 3.11
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

### GPIO

```python
from linuxpy.gpio import Device

with Device.from_id(0) as gpio:
    info = gpio.get_info()
    print(info.name, info.label, len(info.lines))
    l0 = info.lines[0]
    print(f"L0: {l0.name!r} {l0.flags.name}")

# output should look somethig like:
# gpiochip0 INT3450:00 32
# L0: '' INPUT
```

Check the [GPIO user guide](https://tiagocoutinho.github.io/linuxpy/user_guide/gpio/) and
[GPIO reference](https://tiagocoutinho.github.io/linuxpy/api/gpio/) for more information.

### Input

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

Check the [Input user guide](https://tiagocoutinho.github.io/linuxpy/user_guide/input/) and
[Input reference](https://tiagocoutinho.github.io/linuxpy/api/input/) for more information.

### Led

```python
from linuxpy.led import find

caps_lock = find(function="capslock")
print(caps_lock.brightness)
print(caps_lock.max_brightness)
```

Check the [LED user guide](https://tiagocoutinho.github.io/linuxpy/user_guide/led/) and
[LED reference](https://tiagocoutinho.github.io/linuxpy/api/led/) for more information.

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
Check the [MIDI user guide](https://tiagocoutinho.github.io/linuxpy/user_guide/midi/) and
[MIDI reference](https://tiagocoutinho.github.io/linuxpy/api/midi/) for more information.

### Thermal and cooling

```python
from linuxpy.thermal import find
with find(type="x86_pkg_temp") as tz:
    print(f"X86 temperature: {tz.temperature/1000:6.2f} C")
```

Check the [Thermal and cooling user guide](https://tiagocoutinho.github.io/linuxpy/user_guide/thermal/) and
[Thermal and cooling reference](https://tiagocoutinho.github.io/linuxpy/api/thermal/) for more information.

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

Check the [V4L2 user guide](https://tiagocoutinho.github.io/linuxpy/user_guide/video/) and
[V4L2 reference](https://tiagocoutinho.github.io/linuxpy/api/video/) for more information.

[pypi-python-versions]: https://img.shields.io/pypi/pyversions/linuxpy.svg
[pypi-version]: https://img.shields.io/pypi/v/linuxpy.svg
[pypi-status]: https://img.shields.io/pypi/status/linuxpy.svg
[license]: https://img.shields.io/pypi/l/linuxpy.svg
[CI]: https://github.com/tiagocoutinho/linuxpy/actions/workflows/ci.yml/badge.svg
[documentation]: https://img.shields.io/badge/Documentation-blue?color=grey&logo=mdBook
[source]: https://img.shields.io/badge/Source-grey?logo=git
