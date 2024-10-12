---
hide:
  - navigation
---

# 🐧 Welcome to linuxpy


[![linuxpy][pypi-version]](https://pypi.python.org/pypi/linuxpy)
[![Python Versions][pypi-python-versions]](https://pypi.python.org/pypi/linuxpy)
[![License][license]]()
[![CI][CI]](https://github.com/tiagocoutinho/linuxpy/actions/workflows/ci.yml)

[![Source][source]](https://github.com/tiagocoutinho/linuxpy/)
[![Documentation][documentation]](https://tiagocoutinho.github.io/linuxpy/)

Human friendly interface to linux subsystems using python.

Provides python access to several linux subsystems like V4L2, input, GPIO and MIDI.

There is experimental, undocumented, incomplete and unstable access to USB.

Need fine control over Webcams, GPIO, MIDI devices, thermal sensors and cooling
devices, joysticks, gamepads, keyboards, mice or even the keyboard light on
your laptop?

Linuxpy has your back.

Requirements:

* python >= 3.9
* Fairly recent linux kernel
* Installed kernel modules you want to access (ex: *uinput* if you need user space
created input devices)

And yes, it is true: there are **no python** dependencies! Also there are **no
C libraries** dependencies! Everything is done here through direct ioctl, read and
write calls. Ain't linux wonderful?



## Goals

* A **pure** python library (no dependency on other C libraries)
* No third-party python dependencies (not a hard requirement)
* Fine-grain access to low level linux device capabilities
* For video (V4L2) this means:
    * List available devices
    * Obtain detailed information about a device (name, driver,
        capabilities, available formats)
    * Fine control over the camera parameters (ex: resolution, format,
        brightness, contrast, etc)
    * Fine control resource management to take profit of memory map, DMA
        or user pointers (buffers)
    * Detailed information about a frame (timestamp, frame number, etc)
    * Write to VideoOutput
    * Integration with non blocking coroutine based applications (gevent
        and asyncio) without the usual tricks like using `asyncio.to_thread()`

## Installation

From within your favorite python environment:

<div class="termy" data-ty-macos data-ty-title="bash" data-ty-typeDelay="30" >
	<span data-ty="input" data-ty-prompt="$">pip install linuxpy</span>
    <span data-ty="progress" >pip install linuxpy</span>
</div>

To run the examples you'll need:

```console
$ pip install linuxpy[examples]
```

To develop, run tests, build package, lint, etc you'll need:

```console
$ pip install linuxpy[dev]
```

To run docs you'll need:

```console
$ pip install linuxpy[docs]
```

## FAQ

*Most python libraries try as hard as possible to be platform independent.
Why create a library that is explicitly designed to work only on linux?*

Well, first of all, one of the goals is to be able to access low level linux
device capabilities like video controls. Second, I don't have access to
proprietary OS like Windows or MacOS.

If this answer is not enough than think of this library as a low level
dependency on linux systems of other libraries  that will be concerned
with providing a common API on different platforms.



[pypi-python-versions]: https://img.shields.io/pypi/pyversions/linuxpy.svg
[pypi-version]: https://img.shields.io/pypi/v/linuxpy.svg
[pypi-status]: https://img.shields.io/pypi/status/linuxpy.svg
[license]: https://img.shields.io/pypi/l/linuxpy.svg
[CI]: https://github.com/tiagocoutinho/linuxpy/actions/workflows/ci.yml/badge.svg
[documentation]: https://img.shields.io/badge/Documentation-blue?color=grey&logo=mdBook
[source]: https://img.shields.io/badge/Source-grey?logo=git
