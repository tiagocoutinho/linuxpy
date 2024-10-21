#
# This file is part of the linuxpy project
#
# Copyright (c) 2024 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.


"""
line_config = {
    "line": 5,
    "direction": output | input,
    "bias": "" | "pull-up" | "pull-down" | "disabled"
    "clock": "" | "realtime" | "hte" # "" defaults to monotonic, HTE: hardware timestamp engine

    "drive": "" | drain | source,  # direction must be output, "" means push-pull
    "debounce": "" | float # direction must be output; "" means don't set it;

    "edge": "" | "rising" | "falling" | "both"  # direction must be input
}

config = {
    lines: 1 | [1,2,3],

}
"""

import collections
import functools
from collections.abc import Mapping

from linuxpy.types import Collection, Optional, Sequence, Union
from linuxpy.util import index_mask, sentinel, sequence_indexes

from .raw import MAX_ATTRS, LineAttrId, LineFlag, gpio_v2_line_config, gpio_v2_line_request


def check_line_config(line_config: dict):
    line = line_config["line"]
    if not isinstance(line, int) or line < 0:
        raise ValueError("line must be an int > 0")
    direction = line_config.get("direction", "input").upper()
    direction = LineFlag[direction]
    bias = line_config.get("bias", sentinel)
    clock = line_config.get("clock", sentinel)
    active = line_config.get("active", sentinel)

    drive = line_config.get("drive", sentinel)
    debounce = line_config.get("debounce", sentinel)

    edge = line_config.get("edge", sentinel)

    if direction == LineFlag.INPUT:
        if drive is not sentinel:
            raise ValueError("Can only set drive on output lines")
        if debounce is not sentinel:
            raise ValueError("Can only set debounce on output lines")
        if edge is not sentinel:
            if edge.lower() not in ("rising", "falling", "both"):
                raise ValueError("edge must be 'rising', 'falling' or 'both'")
    elif direction == LineFlag.OUTPUT:
        if edge is not sentinel:
            raise ValueError("Can only set edge on input lines")
        if drive is not sentinel:
            if drive.lower() not in ("push-pull", "drain", "source"):
                raise ValueError("drive must be 'drain', 'source' or 'push-pull'")
        if debounce is not sentinel:
            if not isinstance(debounce, float) or debounce < 0:
                raise ValueError("debounce must be a positive number")
    else:
        raise ValueError("direction can only be output or input")

    if active is not sentinel:
        if active.lower() not in ("high", "low"):
            raise ValueError("active must be 'rising', 'high' or 'low'")

    if bias is not sentinel:
        if bias.lower() not in ("pull-up", "pull-down"):
            raise ValueError("bias must be 'pull-up' or 'pull-down'")

    if clock is not sentinel:
        if clock.lower() not in ("monotonic", "realtime", "hte"):
            raise ValueError("drive must be 'monotonic', 'realtime' or 'hte'")


_CONFIG_DIRECTION_MAP: dict[Union[str, LineFlag], LineFlag] = {
    "input": LineFlag.INPUT,
    "output": LineFlag.OUTPUT,
    "none": LineFlag.INPUT,
    "": LineFlag.INPUT,
    LineFlag.INPUT: LineFlag.INPUT,
    LineFlag.OUTPUT: LineFlag.OUTPUT,
}


_CONFIG_EDGE_MAP: dict[Union[str, LineFlag], LineFlag] = {
    "rising": LineFlag.EDGE_RISING,
    "falling": LineFlag.EDGE_FALLING,
    "both": LineFlag.EDGE_RISING | LineFlag.EDGE_FALLING,
    "": LineFlag(0),
    "none": LineFlag(0),
    LineFlag(0): LineFlag(0),
    LineFlag.EDGE_RISING: LineFlag.EDGE_RISING,
    LineFlag.EDGE_FALLING: LineFlag.EDGE_FALLING,
    LineFlag.EDGE_RISING | LineFlag.EDGE_FALLING: LineFlag.EDGE_RISING | LineFlag.EDGE_FALLING,
}


_CONFIG_DRIVE_MAP: dict[Union[str, LineFlag], LineFlag] = {
    "drain": LineFlag.OPEN_DRAIN,
    "source": LineFlag.OPEN_SOURCE,
    "push-pull": LineFlag(0),
    "": LineFlag(0),
    "none": LineFlag(0),
    LineFlag.OPEN_DRAIN: LineFlag.OPEN_DRAIN,
    LineFlag.OPEN_SOURCE: LineFlag.OPEN_SOURCE,
    LineFlag(0): LineFlag(0),
}


_CONFIG_BIAS_MAP: dict[Union[str, LineFlag], LineFlag] = {
    "pull-up": LineFlag.BIAS_PULL_UP,
    "pull-down": LineFlag.BIAS_PULL_DOWN,
    "": LineFlag(0),
    "none": LineFlag(0),
    LineFlag.BIAS_PULL_UP: LineFlag.BIAS_PULL_UP,
    LineFlag.BIAS_PULL_DOWN: LineFlag.BIAS_PULL_DOWN,
    LineFlag(0): LineFlag(0),
}


_CONFIG_CLOCK_MAP: dict[Union[str, LineFlag], LineFlag] = {
    "realtime": LineFlag.EVENT_CLOCK_REALTIME,
    "hte": LineFlag.EVENT_CLOCK_HTE,
    "": LineFlag(0),
    "monotonic": LineFlag(0),
    LineFlag.EVENT_CLOCK_REALTIME: LineFlag.EVENT_CLOCK_REALTIME,
    LineFlag.EVENT_CLOCK_HTE: LineFlag.EVENT_CLOCK_HTE,
    LineFlag(0): LineFlag(0),
}


_CONFIG_ACTIVE: dict[Union[str, LineFlag], LineFlag] = {
    "high": LineFlag(0),
    "low": LineFlag.ACTIVE_LOW,
    LineFlag.ACTIVE_LOW: LineFlag.ACTIVE_LOW,
    "": LineFlag(0),
    LineFlag(0): LineFlag(0),
}


def encode_line_config(line_config: dict) -> tuple[int, LineFlag, Union[int, None]]:
    direction = line_config.get("direction", "input").lower()
    bias = line_config.get("bias", "").lower()
    clock = line_config.get("clock", "").lower()
    drive = line_config.get("drive", "").lower()
    edge = line_config.get("edge", "").lower()
    active = line_config.get("active", "").lower()
    flags = (
        _CONFIG_DIRECTION_MAP[direction]
        | _CONFIG_EDGE_MAP[edge]
        | _CONFIG_DRIVE_MAP[drive]
        | _CONFIG_BIAS_MAP[bias]
        | _CONFIG_CLOCK_MAP[clock]
        | _CONFIG_ACTIVE[active]
    )

    debounce = line_config.get("debounce", None)
    debounce = None if debounce is None else int(debounce * 1_000_000)

    return line_config["line"], flags, debounce


def encode_config_lines(
    lines: Sequence[tuple[int, LineFlag, Union[int, None]]], raw_config: Union[gpio_v2_line_config, None]
) -> gpio_v2_line_config:
    flags = collections.defaultdict(list)
    debounces = collections.defaultdict(list)
    for line, flag, debounce in lines:
        flags[flag].append(line)
        if debounce is not None:
            debounces[debounce].append(line)

    if len(flags) + len(debounces) > MAX_ATTRS:
        raise ValueError("Config exceeds maximum custom")

    if raw_config is None:
        raw_config = gpio_v2_line_config()

    flags_lines = collections.Counter({flag: len(lines) for flag, lines in flags.items()})
    general_flags, _ = flags_lines.most_common(1)[0]
    flags.pop(general_flags)
    raw_config.flags = general_flags

    line_indexes = sequence_indexes(line[0] for line in lines)
    for idx, (flag, flag_lines) in enumerate(flags.items()):
        raw_config.attrs[idx].mask = index_mask(line_indexes, flag_lines)
        raw_config.attrs[idx].attr.id = LineAttrId.FLAGS
        raw_config.attrs[idx].attr.flags = flag

    for idx, (debounce, debounce_lines) in enumerate(debounces.items(), len(flags)):
        raw_config.attrs[idx].mask = index_mask(line_indexes, debounce_lines)
        raw_config.attrs[idx].attr.id = LineAttrId.DEBOUNCE
        raw_config.attrs[idx].attr.debounce_period_us = debounce

    raw_config.num_attrs = len(flags) + len(debounces)

    return raw_config


def encode_config(config: list[dict], raw_config: Union[gpio_v2_line_config, None] = None) -> gpio_v2_line_config:
    lines = [encode_line_config(line_config) for line_config in config]
    return encode_config_lines(lines, raw_config)


def encode_request(config: dict, raw_request: Union[gpio_v2_line_request, None] = None) -> gpio_v2_line_request:
    if raw_request is None:
        raw_request = gpio_v2_line_request()
    raw_request.consumer = config.get("name", "linuxpy").encode()
    config_lines = config["lines"]
    lines = [config_line["line"] for config_line in config_lines]
    raw_request.num_lines = len(lines)
    raw_request.offsets[: len(lines)] = lines

    encode_config(config_lines, raw_request.config)
    return raw_request


def parse_config_line(line):
    if isinstance(line, int):
        return {"line": line}
    return line


def parse_config_lines(lines: Union[Collection, int]) -> list[dict]:
    if isinstance(lines, int):
        lines = [lines]
    if isinstance(lines, dict):
        return [{**cfg, "line": line} for line, cfg in lines.items()]
    if isinstance(lines, (list, tuple)):
        return [parse_config_line(line) for line in lines]
    raise TypeError("lines must be an int, a sequence of int or dict or dict")


def parse_config(config: Optional[Union[Collection, int]], nb_lines: int) -> dict:
    if config is None:
        result = {"lines": tuple(range(nb_lines))}
    elif isinstance(config, int):
        result = {"lines": (config,)}
    elif isinstance(config, Sequence):
        result = {"lines": config}
    elif isinstance(config, Mapping):
        result = config
    else:
        raise TypeError("config must be an int, list or dict")
    result["lines"] = parse_config_lines(result["lines"])
    result.setdefault("name", "linuxpy")
    return result


def CLine(nb, direction="", bias="", drive="", edge="", clock="", debounce=None):
    result = {"line": nb}
    if direction:
        result["direction"] = direction
    if bias:
        result["bias"] = bias
    if drive:
        result["drive"] = drive
    if edge:
        result["edge"] = edge
    if clock:
        result["clock"] = clock
    if debounce is not None:
        result["debounce"] = debounce
    return result


CLineIn = functools.partial(CLine, direction="input")
CLineOut = functools.partial(CLine, direction="output")


def Config(lines, name="linuxpy"):
    return {"name": name, "lines": parse_config_lines(lines)}
