#
# This file is part of the linuxpy project
#
# Copyright (c) 2024 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

"""
## Configfs GPIO Simulator

The configfs GPIO Simulator (gpio-sim) provides a way to create simulated GPIO chips
for testing purposes. The lines exposed by these chips can be accessed using the
standard GPIO character device interface as well as manipulated using sysfs attributes.

To be able to create GPIOSim chips, the user will need permissions.

Here is an example of what to put in /etc/udev/rules.d/80-gpio-sim.rules that gives
access to users belonging to the `input` group:

```
KERNEL=="gpio-sim", SUBSYSTEM=="config", RUN+="/bin/chown -R root:input /sys/kernel/config/gpio-sim"
KERNEL=="gpio-sim", SUBSYSTEM=="config", RUN+="/bin/chmod -R 775 /sys/kernel/config/gpio-sim"
```

See https://www.kernel.org/doc/html/latest/admin-guide/gpio/gpio-sim.html for details
"""

from pathlib import Path

from linuxpy.configfs import CONFIGFS_PATH
from linuxpy.gpio.device import get_chip_info
from linuxpy.types import Optional, Union

GPIOSIM_PATH: Optional[Path] = None if CONFIGFS_PATH is None else CONFIGFS_PATH / "gpio-sim"


def find_gpio_sim_file(num_lines=None) -> Optional[Path]:
    """Best effort to find

    Returns:
        _type_: _description_
    """
    for path in sorted(Path("/dev").glob("gpiochip*"))[::-1]:
        with path.open("rb") as fobj:
            info = get_chip_info(fobj)
            if "gpio-sim" in info.label:
                if num_lines is None or info.lines == num_lines:
                    return path


class GPIOSim:
    def __init__(self, name: str):
        self.name = name
        self.path = GPIOSIM_PATH / self.name
        self.banks = [0]

    def __enter__(self):
        self.configure()
        self.enable()

    def __exit__(self):
        self.disable()
        self.destroy()

    def write(self, fname, value):
        with open(self.path / fname, "wb") as fobj:
            fobj.write(str(value))

    def create_bank(self):
        self.path.mkdir(exist_ok=True)

    def configure(self):
        self.path.mkdir(exist_ok=True)
        for bank in self.banks:
            bname = f"gpio-bank{bank}"
            path = self.path / bname
            path.mkdir(exist_ok=True, mode=0o770)
            self.write(path / "num_lines", 16)

    def destroy(self): ...

    def live(self, value: Union[bool, int]):
        self.write("live", 1 if value else 0)

    def enable(self):
        self.live(1)

    def disable(self):
        self.live(0)
