# Developers corner

## Requirements

A linux OS and python >= 3.9.

From within your favorite python environment:

```console
$ pip install linuxpy[dev]
```

Additionally, to run the code generation tool you'll need `castxml` installed
on your system.

On a debian based run:

```console
$ apt install castxml
```

## Code generation

This project uses an internal simple code generator that reads linux
kernel header files and produces several `raw.py` ctypes based python
files for each sub-system.

To re-generate these files for a newer linux kernel (or fix a bug)
you'll need linux header files installed on your system + black.

To launch the tool call:

```console
$ python -m linuxpy.codegen.cli
```

## Running tests

Some video tests will only run with a properly configured `v4l2loopback`
and `vivid` drivers.

```console
$ sudo modprobe v4l2loopback video_nr=199 card_label="Loopback 199"
$ sudo modprobe vivid n_devs=1 vid_cap_nr=190 vid_out_nr=191 meta_cap_nr=192 meta_out_nr=193
```

Additionally the user which runs the tests will need read/write access to
`/dev/video199` (v4l2loopback) and `/dev/video190`, `/dev/video191`, `/dev/video192`
and `/dev/video193` (for vivid).
On most systems this can be achieved by adding the user to the `video` group:

```console
$ sudo addgroup $USER video
```

Some input tests require the user which runs the tests to have read/write
access to `/dev/uinput`.
On most systems this can be achieved by adding the user to the `input` group:

```console
$ sudo addgroup $USER input
```
