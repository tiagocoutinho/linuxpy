#
# This file is part of the linuxpy project
#
# Copyright (c) 2024 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

from pathlib import Path

from linuxpy.types import Optional

from .mounts import configfs

CONFIGFS_PATH: Optional[Path] = configfs()
