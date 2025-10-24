from common import main
from common_gl import View
from common_glfw import GLFWWindow, frames


def run(capture, fmt, width, height):
    with GLFWWindow("Video GLFW GL", width, height) as win:
        with View() as view:
            for frame in frames(win, capture):
                view.render(frame)


if __name__ == "__main__":
    main(run)
