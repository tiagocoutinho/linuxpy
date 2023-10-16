#
# This file is part of the enjoy project
#
# Copyright (c) 2021 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import asyncio
import logging
import shutil
import time

import beautifultable
import typer

from linuxpy.input.device import EventType, Device, iter_input_files

app = typer.Typer()


def name(code):
    return code.name.split("_", 1)[-1]


def names(codes, sep=" "):
    return sep.join(name(code) for code in codes)


def create_state(dev):
    state = {}
    for event_type, codes in dev.capabilities.items():
        if event_type == EventType.KEY:
            state["keys"] = dev.active_keys
            state["pressed"] = names(state["keys"])
        elif event_type == EventType.ABS:
            state["abs"] = {
                name(code): "{:3d}".format(dev.get_abs_info(code).value)
                for code in codes
            }
        elif event_type == EventType.FF:
            # TODO
            pass
    return state


def create_state_template(state):
    template = []
    if "abs" in state:
        if "X" in state["abs"]:
            text = "X: {abs[X]}"
            if "Y" in state["abs"]:
                text += " Y:{abs[Y]}"
            if "Z" in state["abs"]:
                text += " Z:{abs[Z]}"
            template.append(text)

        if "RX" in state["abs"]:
            template.append("RX: {abs[RX]} RY:{abs[RY]} RZ:{abs[RZ]}")
    if "keys" in state:
        template.append("{pressed}")
    return " | ".join(template)


@app.command()
def table():
    table = beautifultable.BeautifulTable()
    table.maxwidth = shutil.get_terminal_size().columns
    for path in sorted(iter_input_files()):
        with Device(path) as dev:
            caps = ", ".join(name(cap) for cap in dev.capabilities)
            table.rows.append((dev.name, path, caps))
    typer.echo(table)


@app.command()
def listen(path: str):
    fmt = "%(threadName)-10s %(asctime)-15s %(levelname)-5s %(name)s: %(message)s"
    logging.basicConfig(level="INFO", format=fmt)

    CLEAR_LINE = "\r\x1b[0K"

    async def cycle(variable):
        while True:
            await asyncio.sleep(0.1)
            variable[0] += 1

    async def event_loop():
        start = time.monotonic()
        data = [0]
        asyncio.create_task(cycle(data))
        async for event in device:
            new = time.monotonic()
            elapsed = new - start
            if event.type == EventType.KEY:
                keys = state["keys"]
                (keys.add if event.value else keys.discard)(event.code)
                state["pressed"] = names(keys)
            elif event.type == EventType.ABS:
                state["abs"][name(event.code)] = f"{event.value:3d}"
            elif event.type == EventType.FF:
                # TODO
                pass
            else:
                continue
            print(CLEAR_LINE, end="")
            print(template.format(**state), end="")
            print(f" | data={data[0]}; {elapsed=:.2f} s", end="", flush=True)



    with Device(path) as device:
        state = create_state(device)
        template = create_state_template(state)
        asyncio.run(event_loop())


@app.command()
def info(path: str):
    with Device(path) as dev:
        typer.echo(dev.name)
        for cap, items in dev.capabilities.items():
            items = ", ".join(item.name.rsplit("_", 1)[-1] for item in items)
            typer.echo("{}: {}".format(cap.name, items))


if __name__ == "__main__":
    app()
