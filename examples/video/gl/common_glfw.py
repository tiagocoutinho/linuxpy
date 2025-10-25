import glfw
from common import maybe_frames


class GLFWWindow:
    def __init__(self, name, width, height):
        self.name = name
        self.width = width
        self.height = height
        self.win = None

    def __enter__(self):
        glfw.init()
        self.win = glfw.create_window(self.width, self.height, self.name, None, None)
        glfw.make_context_current(self.win)
        return self

    def __exit__(self, *args):
        pass


def frames(win, capture):
    with capture:
        stream = maybe_frames(capture)
        while not glfw.window_should_close(win.win):
            yield next(stream)
            glfw.swap_buffers(win.win)
            glfw.poll_events()
