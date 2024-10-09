import json
import pathlib
import sys

mounts = pathlib.Path("/proc/mounts")
for dtype, mpath, fstype, *_ in mounts.read_text().splitlines():
    if dtype == "configfs" and fstype == "configfs":
        CONFIGFS_PATH = pathlib.Path(mpath)
else:
    CONFIGFS_PATH = pathlib.Path("/sys/kernel/config/gpio-sim")


def Line(name, direction=None):
    result = {"name": name}
    if direction:
        result["hog"] = {"name": f"{name}-hog", "direction": direction}
    return result


DEFAULT = {
    "name": "chip99",
    "banks": [
        {
            "lines": [
                Line("L-I0"),
                Line("L-I1"),
                Line("L-I2", "input"),
                Line("L-O0", "output-high"),
                Line("L-O1", "output-low"),
            ]
        },
    ],
}


if len(sys.argv) > 1:
    cfg = json.load(sys.argv[-1])
else:
    cfg = DEFAULT


def mkdir(path):
    print(f"Creating {path}")
    path.mkdir()


path = CONFIGFS_PATH / cfg["name"]
live = path / "live"

# clean up first
if path.exists():
    live.write_text("0")
    for directory, _, _ in path.walk(top_down=False):
        directory.rmdir()


mkdir(path)
for bank_id, bank in enumerate(cfg["banks"]):
    lines = bank["lines"]

    bpath = path / f"gpio-bank{bank_id}"
    mkdir(bpath)
    blabel = bank.get("name", f"gpio-sim-bank{bank_id}")

    (bpath / "num_lines").write_text("16")
    (bpath / "label").write_text(blabel)
    for line_id, line in enumerate(lines):
        lpath = bpath / f"line{line_id}"
        mkdir(lpath)
        (lpath / "name").write_text(line.get("name", f"L-{line_id}"))
        if hog := line.get("hog"):
            hpath = lpath / "hog"
            mkdir(hpath)
            (hpath / "name").write_text(hog["name"])
            (hpath / "direction").write_text(hog["direction"])


live.write_text("1")
