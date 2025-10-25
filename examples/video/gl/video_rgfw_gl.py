from common import main
from common_gl import View
from common_rgfw import RGFWWindow, frames


def run(capture, fmt, width, height):
    with RGFWWindow("Video RGFW GL", width, height) as win:
        with View() as view:
            for frame in frames(win, capture):
                view.render(frame)


if __name__ == "__main__":
    main(run)
