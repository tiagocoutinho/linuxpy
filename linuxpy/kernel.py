#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import platform

release = platform.release()

VERSION = tuple(int(i) for i in release.split("-")[0].split("."))
