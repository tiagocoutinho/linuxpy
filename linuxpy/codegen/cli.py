import logging

from .input import main as input_run
from .magic import main as magic_run
from .usbfs import main as usbfs_run
from .usbids import main as usbids_main
from .video import main as video_main


def main():
    logging.basicConfig(level="INFO")

    magic_run()
    input_run()
    video_main()
    usbfs_run()
    usbids_main()


if __name__ == "__main__":
    main()
