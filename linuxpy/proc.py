from pathlib import Path

from linuxpy.util import try_numeric

PROC_PATH = Path("/proc")

CPU_INFO_PATH: Path = PROC_PATH / "cpuinfo"
MEM_INFO_PATH: Path = PROC_PATH / "meminfo"
MODULES_PATH: Path = PROC_PATH / "modules"


def iter_cpu_info():
    data = CPU_INFO_PATH.read_text()
    for cpu in data.split("\n\n"):
        info = {}
        for line in cpu.splitlines():
            key, value = map(str.strip, line.split(":", 1))
            if "flags" in key or key == "bugs":
                value = value.split()
            else:
                value = try_numeric(value)
            info[key] = value
        yield info


def iter_mem_info():
    data = MEM_INFO_PATH.read_text()
    for line in data.splitlines():
        key, value = map(str.strip, line.split(":", 1))
        if value.endswith(" kB"):
            value = try_numeric(value[:-3]) * 1024
        else:
            value = try_numeric(value)
        yield key, value


def iter_modules():
    data = MODULES_PATH.read_text()
    for line in data.splitlines():
        fields = line.split()
        mod = {
            "name": fields[0],
            "size": int(fields[1]),
            "use_count": int(fields[2]),
            "dependencies": [] if fields[3] == "-" else [dep for dep in fields[3].split(",") if dep],
        }
        if len(fields) > 5:
            mod["state"] = fields[4]
            mod["offset"] = int(fields[5], 16)
        yield mod
