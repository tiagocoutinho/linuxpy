from common import RGFWCaptureWindow, RGFWWindow, main
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
        width * height * b"\xff\x00\x00",
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
    GL.glTextureSubImage2D(
        texture_id,
        0,
        0,
        0,
        frame.width,
        frame.height,
        GL.GL_BGR,
        UBYTE,
        frame.user_data,
    )


def run(capture):
    fmt = capture.get_format()
    width = 1980
    height = width * fmt.height // fmt.width
    with RGFWWindow("Video RGFW GL", 0, 0, width, height) as win:
        GL.glEnable(TEXTURE_2D)
        texture_id = create_texture(fmt.width, fmt.height)
        for frame in RGFWCaptureWindow(capture, win):
            if frame:
                update_texture(texture_id, frame)
            draw_canvas()
        destroy_texture(texture_id)


if __name__ == "__main__":
    main(run)
