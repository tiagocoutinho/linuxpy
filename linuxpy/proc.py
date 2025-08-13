#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

from pathlib import Path

from linuxpy.util import try_numeric

PROC_PATH = Path("/proc")

CPU_INFO_PATH: Path = PROC_PATH / "cpuinfo"
MEM_INFO_PATH: Path = PROC_PATH / "meminfo"
MODULES_PATH: Path = PROC_PATH / "modules"
STAT_PATH: Path = PROC_PATH / "stat"
NET_PATH: Path = PROC_PATH / "net"
DEV_PATH: Path = NET_PATH / "dev"
WIRELESS_PATH: Path = NET_PATH / "wireless"
NETSTAT_PATH = NET_PATH / "netstat"
SNMP_PATH = NET_PATH / "snmp"


def _iter_read_kv(path: Path):
    with path.open() as fobj:
        lines = fobj.readlines()
    for keys, values in zip(lines[::2], lines[1::2], strict=True):
        key, *keys = keys.split()
        value, *values = values.split()
        assert key == value
        yield key.rstrip(":"), dict(zip(keys, [int(value) for value in values], strict=True))


def iter_cpu_info():
    """
    Iterate over CPU info. Each item represents the information about one of
    the processors in the system.
    """
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


def cpu_info():
    """
    CPU info as a sequence of dictionaries, each with information about one of
    the system processors.
    """
    return tuple(iter_cpu_info())


def iter_mem_info():
    """
    Iterate over the system memory information. Each item is a pair of field name and field value.
    """
    data = MEM_INFO_PATH.read_text()
    for line in data.splitlines():
        key, value = map(str.strip, line.split(":", 1))
        if value.endswith(" kB"):
            value = try_numeric(value[:-3]) * 1024
        else:
            value = try_numeric(value)
        yield key, value


def mem_info():
    """
    System memory information.
    """
    return dict(iter_mem_info())


def iter_modules():
    """
    Iterate over system modules. Each item represents the information about one of
    the modules in the system.
    """
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


def modules():
    """
    Modules info as a sequence of dictionaries, each with information about one of
    the system modules.
    """
    return tuple(iter_modules())


def iter_stat():
    """
    Iterate over the system stats information. Each item is a pair of field name and field value.
    """
    CPU = "user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal", "guest", "guest_nice"
    data = STAT_PATH.read_text()
    for line in data.splitlines():
        name, *fields = line.split()
        if name.startswith("cpu"):
            payload = dict(zip(CPU, map(int, fields), strict=True))
        elif name in {"intr", "softirq"}:
            total, *fields = (int(field) for field in fields)
            payload = dict(enumerate(fields, start=1))
            payload["total"] = total
        elif name in {"ctxt", "btime", "processes", "procs_running", "procs_blocked"}:
            payload = int(fields[0])
        else:
            continue
        yield name, payload


def stat():
    """
    System stats information.
    """
    return dict(iter_stat())


def iter_dev():
    """
    Iterate over network devices. Each item represents the information about one of
    the network devices in the system.
    """
    with DEV_PATH.open() as fobj:
        lines = fobj.readlines()
    # Skip the header lines (usually first 2 lines)
    for line in lines[2:]:
        fields = line.strip().split()
        if not fields:
            continue
        yield {
            "interface": fields[0].rstrip(":"),
            "receive": {
                "bytes": int(fields[1]),
                "packets": int(fields[2]),
                "errs": int(fields[3]),
                "drop": int(fields[4]),
                "fifo": int(fields[5]),
                "frame": int(fields[6]),
                "compressed": int(fields[7]),
                "multicast": int(fields[8]),
            },
            "transmit": {
                "bytes": int(fields[9]),
                "packets": int(fields[10]),
                "errs": int(fields[11]),
                "drop": int(fields[12]),
                "fifo": int(fields[13]),
                "colls": int(fields[14]),
                "carrier": int(fields[15]),
                "compressed": int(fields[16]),
            },
        }


def dev():
    """
    Network devices info as a sequence of dictionaries, each with information about one of
    the system network devices.
    """
    return tuple(iter_dev())


def iter_wireless():
    """
    Iterate over wireless network devices. Each item represents the information about one of
    the wireless network devices in the system.
    """
    with WIRELESS_PATH.open() as fobj:
        lines = fobj.readlines()
    # Skip the header lines (usually first 2 lines)
    for line in lines[2:]:
        fields = line.strip().split()
        if not fields:
            continue
        yield {
            "interface": fields[0].rstrip(":"),
            "status": int(fields[1], 16),
            "quality": {
                "link": int(fields[2].rstrip(".")),
                "level": int(fields[3].rstrip(".")),
                "noise": int(fields[4].rstrip(".")),
            },
            "discarded": {
                "nwid": int(fields[5]),
                "crypt": int(fields[6]),
                "misc": int(fields[7]),
            },
        }


def wireless():
    """
    Wireless netowrk devices info as a sequence of dictionaries, each with information about one of
    the system wireless network devices.
    """
    return tuple(iter_wireless())


def iter_netstat():
    """
    Iterate over network statistics.
    """
    return _iter_read_kv(NETSTAT_PATH)


def netstat():
    """
    Network statistics.
    """
    return dict(iter_netstat())


def iter_snmp():
    """
    Iterate over SNMP statistics.
    """
    return _iter_read_kv(SNMP_PATH)


def snmp():
    """
    SNMP statistics.
    """
    return dict(iter_snmp())
