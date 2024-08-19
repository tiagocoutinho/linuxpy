import sys

if len(sys.argv) != 2:
    print("Requires <device-name> argument", file=sys.stderr)
    sys.exit(1)

import logging

from linuxpy.led import ULED

logging.basicConfig(level="WARNING", format="%(asctime)-15s: %(message)s")

try:
    with ULED(sys.argv[1], max_brightness=100) as uled:
        for brightness in uled.stream():
            logging.warning("%d", brightness)
except KeyboardInterrupt:
    pass
