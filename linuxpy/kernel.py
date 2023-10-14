import platform

release = platform.release()

VERSION = tuple(int(i) for i in release.split("-")[0].split("."))
