#
# This file is part of the linuxpy project
#
# Copyright (c) 2024 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.


from linuxpy.device import BaseDevice


class Device(BaseDevice):
    PREFIX = "/dev/spidev"
