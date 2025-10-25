import struct

import moderngl as mgl
from OpenGL import GL

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


class View:
    def __init__(self, width, height):
        self.ctx = None
        self.texture = None
        self.width = width
        self.height = height

    def __enter__(self):
        self.ctx = mgl.create_context()
        self.ctx.enable(mgl.DEPTH_TEST)
        self.ctx.viewport = (0, 0, self.width, self.height)
        self.program = self.ctx.program(vertex_shader=VS, fragment_shader=FS)
        self.vao = create_vertex_array(self.program)
        return self

    def render(self, frame):
        self.ctx.clear(0, 0, 1, 1)
        if frame:
            if self.texture is None:
                self.texture = self.ctx.texture((frame.width, frame.height), 3)
            data, fmt = frame.user_data
            self.texture.swizzle = "rgb1" if fmt == GL.GL_RGB else "bgr1"
            self.texture.write(data)
            self.texture.use()
        self.vao.render(mgl.TRIANGLE_FAN)

    def __exit__(self, *args):
        if self.texture:
            self.texture.release()
            self.texture = None
        self.vao.release()
        self.program.release()
