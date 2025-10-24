import struct

import moderngl as mgl
from common import RGFWCaptureWindow, RGFWWindow, main

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

# point:2f uv:2f
VERTICES = (-1, -1, 0, 1, 1, -1, 1, 1, 1, 1, 1, 0, -1, 1, 0, 0)


def create_vertex_array(prog):
    vertices = struct.pack("16f", *VERTICES)
    vbo = prog.ctx.buffer(vertices)
    return prog.ctx.vertex_array(prog, [(vbo, "2f 2f", "pos", "tex")])


def run(capture):
    fmt = capture.get_format()
    aspect = fmt.height / fmt.width
    width = 1980
    height = int(width * aspect)
    with RGFWWindow(f"RGFW ModernGL capture on {capture.device.filename}", 0, 0, width, height) as win:
        ctx = mgl.create_context()
        ctx.enable(mgl.DEPTH_TEST)
        ctx.viewport = (0, 0, width, height)
        texture = ctx.texture((fmt.width, fmt.height), 3)
        prog = ctx.program(vertex_shader=VS, fragment_shader=FS)
        vao = create_vertex_array(prog)
        for frame in RGFWCaptureWindow(capture, win):
            ctx.clear(0, 0, 1, 1)
            if frame:
                texture.write(frame.user_data)
                texture.swizzle = "bgr1"
                texture.use()
            vao.render(mgl.TRIANGLE_FAN)
            win.swapBuffers()


if __name__ == "__main__":
    main(run)
