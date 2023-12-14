# Welcome to linuxpy

[![linuxpy][pypi-version]](https://pypi.python.org/pypi/linuxpy)
[![Python Versions][pypi-python-versions]](https://pypi.python.org/pypi/linuxpy)
[![License][license]]()
[![CI][CI]](https://github.com/tiagocoutinho/linuxpy/actions/workflows/ci.yml)

Human friendly interface to linux subsystems using python.

Provides python access to several linux subsystems like V4L2, input and MIDI.

There is experimental, incomplete and unstable access to USB.

Need fine control over Webcams, MIDI devices, input devices (joysticks,
gamepads, keyboards, mice or even the keyboard light on your laptop)?
Linuxpy has your back.

Only works on python >= 3.9.

## Installation

From within your favorite python environment:

<!-- termynal -->

```console
$ pip install linuxpy
---> 100%
```

To run the examples you'll need:

<!-- termynal -->

```console
$ pip install linuxpy[examples]
---> 100%
```

To develop, run tests, build package, lint, etc you'll need:

<!-- termynal -->

```console
$ pip install linuxpy[dev]
---> 100%
```

To run docs you'll need:

<!-- termynal -->

```console
$ pip install linuxpy[docs]
---> 100%
```

[pypi-python-versions]: https://img.shields.io/pypi/pyversions/linuxpy.svg
[pypi-version]: https://img.shields.io/pypi/v/linuxpy.svg
[pypi-status]: https://img.shields.io/pypi/status/linuxpy.svg
[license]: https://img.shields.io/pypi/l/linuxpy.svg
[CI]: https://github.com/tiagocoutinho/linuxpy/actions/workflows/ci.yml/badge.svg
