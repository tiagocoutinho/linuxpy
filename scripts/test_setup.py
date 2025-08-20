from pathlib import Path
from subprocess import run
from sys import argv

user_group = None if len(argv) < 2 else argv[1]
input_group = user_group or "input"
video_group = user_group or "video"

RULES = f"""\
KERNEL=="uinput", SUBSYSTEM=="misc" GROUP="{input_group}", MODE="0666"
KERNEL=="event[0-9]*", SUBSYSTEM=="input" GROUP="{input_group}", MODE="0666"

KERNEL=="uleds", GROUP="input", MODE="0664"
SUBSYSTEM=="leds", ACTION=="add", RUN+="/bin/chmod -R g=u,o=u /sys%p"
SUBSYSTEM=="leds", ACTION=="change", ENV{{TRIGGER}}!="none", RUN+="/bin/chmod -R g=u,o=u /sys%p"

SUBSYSTEM=="video4linux" GROUP="{video_group}", MODE="0666"

KERNEL=="gpiochip[0-9]*", SUBSYSTEM=="gpio", GROUP="{input_group}", MODE="0666"
"""

MODULES = {
    "uinput": "",
    "uleds": "",
    "gpio-sim": "",
    "vivid": "n_devs=1 node_types=0xe1d3d vid_cap_nr=190 vid_out_nr=191 meta_cap_nr=192 meta_out_nr=193",
    "snd_seq_midi": "",
}


def loaded_modules():
    return {line.split()[0] for line in Path("/proc/modules").read_text().splitlines()}


LOADED_MODULES = loaded_modules()


def handle_rules():
    print("Checking rules")
    rules = Path("/etc/udev/rules.d/99-linuxpy.rules")
    if rules.exists() and RULES in rules.read_text():
        print(" Already prepared")
    else:
        print(f"  Writing rules {rules}")
        rules.write_text(RULES)
        print("  Reloading rules")
        run("udevadm control --reload-rules".split())
        run("udevadm trigger".split())


def handle_module(mod_name):
    print(f"Handling {mod_name}")
    if mod_name in LOADED_MODULES:
        print(f"  Unloading {mod_name}")
        run(f"modprobe -r {mod_name}".split())
    args = MODULES[mod_name]
    print(f"  Loading {mod_name}")
    run(f"modprobe {mod_name} {args}".split())


def handle_gpio_sim():
    print("Preparing GPIO sim")
    mounts = Path("/proc/mounts")
    for dtype, mpath, fstype, *_ in mounts.read_text().splitlines():
        if dtype == "configfs" and fstype == "configfs":
            CONFIGFS_PATH = Path(mpath)
    else:
        CONFIGFS_PATH = Path("/sys/kernel/config/gpio-sim")

    def Line(name, direction=None):
        result = {"name": name}
        if direction:
            result["hog"] = {"name": f"{name}-hog", "direction": direction}
        return result

    cfg = {
        "name": "chip99",
        "banks": [
            {
                "lines": [
                    Line("L-I0"),
                    Line("L-I1"),
                    Line("L-I2", "input"),
                    Line("L-O0", "output-high"),
                    Line("L-O1", "output-low"),
                    Line("L-O2"),
                ]
            },
        ],
    }

    def mkdir(path):
        print(f"  Creating {path}")
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


handle_rules()

for mod_name in MODULES:
    handle_module(mod_name)

handle_gpio_sim()
