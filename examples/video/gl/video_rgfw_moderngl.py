from common import main
from common_moderngl import View
from common_rgfw import RGFWWindow, frames


def run(capture, fmt, width, height):
    with RGFWWindow(f"RGFW ModernGL capture on {capture.device.filename}", width, height) as win:
        with View(width, height) as view:
            for frame in frames(win, capture):
                view.render(frame)


if __name__ == "__main__":
    main(run)
