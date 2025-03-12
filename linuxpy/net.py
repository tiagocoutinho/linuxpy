from pathlib import Path

from .proc import PROC_PATH

NET_PATH: Path = PROC_PATH / "net"
DEV_PATH: Path = NET_PATH / "dev"
WIRELESS_PATH: Path = NET_PATH / "wireless"
NETSTAT_PATH = NET_PATH / "netstat"
SNMP_PATH = NET_PATH / "snmp"


def iter_read_kv(path: Path):
    with path.open() as fobj:
        lines = fobj.readlines()
    for keys, values in zip(lines[::2], lines[1::2]):
        key, *keys = keys.split()
        value, *values = values.split()
        assert key == value
        yield key.rstrip(":"), dict(zip(keys, [int(value) for value in values]))


def iter_dev():
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


def iter_wireless():
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


def iter_netstat():
    return iter_read_kv(NETSTAT_PATH)


def iter_snmp():
    return iter_read_kv(SNMP_PATH)
