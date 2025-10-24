import struct

import moderngl as mgl
import RGFW
from common import main, maybe_frames

VS = """
#version 330 core
in vec2 pos;
in vec2 tex;
out vec2 fragTex;

void main() {
    gl_Position = vec4(pos, 0.0, 1.0);
    fragTex = tex;
}
"""

FS = """
#version 330 core
in vec2 fragTex;
out vec4 fragColor;
uniform sampler2D texS;

void main() {
    fragColor = texture(texS, fragTex);
}
"""


def handle_events(win):
    while win.checkEvent():
        if win.event.type == RGFW.quit or RGFW.isPressed(win, RGFW.Escape):
            win.close()
            return False
    return True


def create_vertex_array(prog):
    vertices = struct.pack(
        "16f",
        -1,
        -1,
        0,
        1,
        1,
        -1,
        1,
        1,
        1,
        1,
        1,
        0,
        -1,
        1,
        0,
        0,
    )
    vbo = prog.ctx.buffer(vertices)
    return prog.ctx.vertex_array(prog, [(vbo, "2f 2f", "pos", "tex")])


def run(capture):
    fmt = capture.get_format()
    aspect = fmt.height / fmt.width
    width = 1980
    height = int(width * aspect)
    stream = iter(capture)
    win = RGFW.createWindow("name", RGFW.rect(0, 0, width, height), RGFW.CENTER)
    ctx = mgl.create_context()
    ctx.enable(mgl.DEPTH_TEST)
    ctx.viewport = (0, 0, width, height)
    texture = ctx.texture((fmt.width, fmt.height), 3)
    prog = ctx.program(vertex_shader=VS, fragment_shader=FS)
    vao = create_vertex_array(prog)

    with capture:
        stream = maybe_frames(capture)
        while True:
            ctx.clear(0, 0, 1, 1)
            if not handle_events(win):
                return
            if frame := next(stream):
                texture.write(frame.data)
                texture.use()
            vao.render(mgl.TRIANGLE_FAN)
            win.swapBuffers()


if __name__ == "__main__":
    main(run)
