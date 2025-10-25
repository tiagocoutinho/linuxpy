# Developers corner

## Requirements

A linux OS and python >= 3.11.

From within your favorite python environment:

```console
$ pip install linuxpy[dev]
```

Additionally, to run the code generation tool you'll need `castxml` installed
on your system.

On a debian based run:

```console
$ apt install castxml linux-headers-$(uname -r)
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

First make sure your user belongs to `input` and `video` groups (create those
groups if they don't exist):

```console
$ sudo addgroup input
$ sudo addgroup video
$ sudo addgroup led
$ sudo adduser $USER input
$ sudo adduser $USER video
$ sudo adduser $USER led
```

(reboot if necessary for those changes to take effect)

Change the udev rules so these groups have access to the devices used by tests:

Create a new rules file (ex: `/etc/udev/rules.d/80-device.rules`):

```
KERNEL=="event[0-9]*", SUBSYSTEM=="input", GROUP="input", MODE:="0660"
KERNEL=="uinput", SUBSYSTEM=="misc", GROUP="input", MODE:="0660"

SUBSYSTEM=="video4linux", GROUP="video", MODE:="0660"

KERNEL=="uleds", GROUP="input", MODE:="0660"
SUBSYSTEM=="leds", ACTION=="add", RUN+="/bin/chmod -R g=u,o=u /sys%p"
SUBSYSTEM=="leds", ACTION=="change", ENV{TRIGGER}!="none", RUN+="/bin/chmod -R g=u,o=u /sys%p"

KERNEL=="gpiochip[0-9]*", SUBSYSTEM=="gpio", GROUP="input", MODE="0660"
ACTION=="add", SUBSYSTEM=="configfs", KERNEL=="gpio-sim", RUN+="/bin/chmod 775 /sys/kernel/config/gpio-sim/%k"
ACTION=="add", SUBSYSTEM=="configfs", KERNEL=="gpio-sim", RUN+="/bin/chown root:input /sys/kernel/config/gpio-sim/%k"
```

Reload the rules:

```console
$ sudo udevadm control --reload-rules
$ sudo udevadm trigger
```

Finally, make sure all kernel modules are installed:

```console
$ sudo modprobe uinput
$ sudo modprobe uleds
$ sudo modprobe -r vivid
$ sudo modprobe vivid n_devs=1 vid_cap_nr=190 vid_out_nr=191 meta_cap_nr=192 meta_out_nr=193
$ sudo modprobe gpio-sim
$ sudo python scripts/setup-gpio-sim.py
```
