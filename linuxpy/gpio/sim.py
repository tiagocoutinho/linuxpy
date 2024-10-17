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

import logging
from pathlib import Path

from linuxpy.configfs import CONFIGFS_PATH
from linuxpy.gpio.device import get_chip_info
from linuxpy.types import Optional

GPIOSIM_PATH: Optional[Path] = None if CONFIGFS_PATH is None else CONFIGFS_PATH / "gpio-sim"

log = logging.getLogger("gpio-sim")


def find_gpio_sim_file(num_lines=None) -> Optional[Path]:
    """Best effort to find

    Returns:
        _type_: _description_
    """
    for path in sorted(Path("/dev").glob("gpiochip*")):
        with path.open("rb") as fobj:
            info = get_chip_info(fobj)
            if "gpio-sim" in info.label:
                if num_lines is None or info.lines == num_lines:
                    return path


def mkdir(path):
    log.info("Creating %s", path)
    path.mkdir()


def rmdir(path):
    log.info("Removing %s", path)
    path.rmdir()


class Device:
    def __init__(self, config):
        self.config = config
        self.path: Path = GPIOSIM_PATH / config["name"]

    @property
    def live_path(self) -> Path:
        return self.path / "live"

    def cleanup(self):
        if self.path.exists():
            self.live_path.write_text("0")
            for directory, _, _ in self.path.walk(top_down=False):
                directory.rmdir()

    def load_config(self):
        mkdir(self.path)

        for bank_id, bank in enumerate(self.config["banks"]):
            lines = bank["lines"]

            bpath = self.path / f"gpio-bank{bank_id}"
            mkdir(bpath)
            blabel = bank.get("name", f"gpio-sim-bank{bank_id}")

            (bpath / "num_lines").write_text("16")
            (bpath / "label").write_text(blabel)
            for line_id, line in enumerate(lines):
                lpath = bpath / f"line{line_id}"
                mkdir(lpath)
                (lpath / "name").write_text(line.get("name", f"L-{line_id}"))
                if hog := line.get("hog"):
                    hpath = lpath / "hog"
                    mkdir(hpath)
                    (hpath / "name").write_text(hog["name"])
                    (hpath / "direction").write_text(hog["direction"])

    @property
    def live(self):
        path = self.live_path
        return path.exists() and int(self.live_path.read_bytes()) != 0
