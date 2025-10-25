#
# This file is part of the linuxpy project
#
# Copyright (c) 2025 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import time

from linuxpy.thermal import iter_thermal_zone_devices


def main():
    def acq():
        for dev in sorted(iter_thermal_zone_devices(), key=lambda dev: dev.type):
            yield dev, dev.temperature

    while True:
        read = acq()
        print(" | ".join(f"{dev.type} = {temp / 1000:6.2f}" for dev, temp in read), end="\r")
        time.sleep(0.1)


if __name__ == "__main__":
    main()
