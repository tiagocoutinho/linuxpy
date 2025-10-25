from OpenGL import GL

TEXTURE_2D = GL.GL_TEXTURE_2D
RGB = GL.GL_RGB
UBYTE = GL.GL_UNSIGNED_BYTE


def create_texture(width, height):
    texture_id = GL.glGenTextures(1)
    GL.glBindTexture(TEXTURE_2D, texture_id)
    GL.glTexParameteri(TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
    GL.glTexParameteri(TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
    GL.glTexParameteri(TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
    GL.glTexParameteri(TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
    # Initial upload (use glTexImage2D only once)
    GL.glTexImage2D(
        TEXTURE_2D,
        0,
        RGB,
        width,
        height,
        0,
        RGB,
        UBYTE,
        None,
    )
    return texture_id


def destroy_texture(texture_id):
    GL.glDeleteTextures(1, [texture_id])


def draw_canvas():
    GL.glBegin(GL.GL_QUADS)
    GL.glTexCoord2f(0.0, 1.0)
    GL.glVertex3f(-1.0, -1.0, 0.0)

    GL.glTexCoord2f(1.0, 1.0)
    GL.glVertex3f(1.0, -1.0, 0.0)

    GL.glTexCoord2f(1.0, 0.0)
    GL.glVertex3f(1.0, 1.0, 0.0)

    GL.glTexCoord2f(0.0, 0.0)
    GL.glVertex3f(-1.0, 1.0, 0.0)
    GL.glEnd()


def update_texture(texture_id, frame):
    data, format = frame.user_data
    GL.glTextureSubImage2D(
        texture_id,
        0,
        0,
        0,
        frame.width,
        frame.height,
        format,
        UBYTE,
        data,
    )


def init_gl():
    GL.glEnable(TEXTURE_2D)


class View:
    def __init__(self):
        self.texture = None

    def __enter__(self):
        init_gl()
        return self

    def render(self, frame):
        if frame:
            if self.texture is None:
                self.texture = create_texture(frame.width, frame.height)
            update_texture(self.texture, frame)
        draw_canvas()

    def __exit__(self, *args):
        destroy_texture(self.texture)
