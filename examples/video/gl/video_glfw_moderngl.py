from common import main
from common_glfw import GLFWWindow, frames
from common_moderngl import View


def run(capture, fmt, width, height):
    with GLFWWindow("Video GLFW GL", width, height) as win:
        with View(width, height) as view:
            for frame in frames(win, capture):
                view.render(frame)


if __name__ == "__main__":
    main(run)
