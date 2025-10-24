import RGFW
from common import maybe_frames


class RGFWWindow:
    def __init__(self, name, width, height):
        self.name = name
        self.rect = RGFW.rect(0, 0, width, height)
        self.win = None

    def handle_events(self):
        while self.win.checkEvent():
            if self.win.event.type == RGFW.quit or RGFW.isPressed(self.win, RGFW.Escape):
                return False
        return True

    def __enter__(self):
        self.win = RGFW.createWindow(self.name, self.rect, RGFW.CENTER)
        return self

    def __exit__(self, *args):
        self.win.close()
        self.win = None


def frames(win, capture):
    with capture:
        stream = maybe_frames(capture)
        while True:
            if not win.handle_events():
                break
            yield next(stream)
            win.win.swapBuffers()
