#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import asyncio
import os
import pathlib
import uuid
from contextlib import contextmanager

from ward import fixture, raises, skip, test

from linuxpy.input.device import (
    Device,
    EventType,
    Grab,
    Key,
    UGamepad,
    UMouse,
    async_event_batch_stream,
    find_gamepad,
    find_mouse,
    is_uinput_available,
)


@contextmanager
def wait_for_new_device():
    base_dir = pathlib.Path("/dev/input")
    assert base_dir.is_dir()
    before = set(base_dir.glob("event*"))

    async def wait():
        while True:
            await asyncio.sleep(0.01)
            new = set(base_dir.glob("event*")) - before
            if new:
                assert len(new) == 1
                filename = new.pop()
                if os.access(filename, os.W_OK):
                    return Device(filename)

    yield wait


@fixture
async def gamepad():
    name = uuid.uuid4().hex
    with wait_for_new_device() as device_finder:
        with UGamepad(name=name) as simulator:
            assert not simulator.closed
            device = await device_finder()
            yield device, simulator


@fixture()
async def mouse():
    name = uuid.uuid4().hex
    with wait_for_new_device() as device_finder:
        with UMouse(name=name) as simulator:
            assert not simulator.closed
            device = await device_finder()
            yield device, simulator


@skip(when=not is_uinput_available(), reason="uinput is not available")
@test("find gamepad")
async def _():
    name = uuid.uuid4().hex
    with wait_for_new_device() as device_finder:
        with UGamepad(name=name) as simulator:
            await device_finder()
            device = find_gamepad(name=name)
            caps = device.capabilities
            del caps[EventType.SYN]
            assert device.name == simulator.name
            assert caps == simulator.CAPABILITIES


@test("find mouse")
async def _():
    name = uuid.uuid4().hex
    with wait_for_new_device() as device_finder:
        with UMouse(name=name) as simulator:
            await device_finder()
            device = find_mouse(name=name)
            caps = device.capabilities
            del caps[EventType.SYN]
            assert device.name == simulator.name
            assert caps == simulator.CAPABILITIES


@skip(when=not is_uinput_available(), reason="uinput is not available")
@test("open/close")
def _(pair_dev_simulator=gamepad):
    dev, _ = pair_dev_simulator
    assert dev.closed
    # closing closed has no effect
    dev.close()
    assert dev.closed

    # open does open it
    dev.open()
    assert not dev.closed

    # opening already opened has no effect
    dev.open()
    assert not dev.closed

    dev.close()
    assert dev.closed

    # Context manager works
    with dev:
        assert not dev.closed
    assert dev.closed

    # Reentrant context manager works
    with dev:
        assert not dev.closed
        with dev:
            assert not dev.closed
        assert not dev.closed
    assert dev.closed


@skip(when=not is_uinput_available(), reason="uinput is not available")
@test("properties")
def _(pair_dev_simulator=gamepad):
    device, simulator = pair_dev_simulator
    with device:
        assert device.device_id.bustype == simulator.bustype
        assert device.device_id.vendor == simulator.vendor_id
        assert device.device_id.product == simulator.product_id
        assert device.version > 0
        assert isinstance(device.x, int)
        assert isinstance(device.y, int)
        assert isinstance(device.rx, int)
        assert isinstance(device.ry, int)
        assert isinstance(device.rz, int)
        assert not device.active_keys


@skip(when=not is_uinput_available(), reason="uinput is not available")
@test("grab")
def _(pair_dev_simulator=gamepad):
    device, simulator = pair_dev_simulator
    with device:
        with Grab(device):
            assert device.device_id.bustype == simulator.bustype

        device.grab()
        assert device.device_id.bustype == simulator.bustype
        device.ungrab()

        with Grab(device):
            with raises(OSError):
                device.grab()


@skip(when=not is_uinput_available(), reason="uinput is not available")
@test("button event")
def _(pair_dev_simulator=gamepad):
    dev, simulator = pair_dev_simulator
    with dev:
        stream = iter(dev)
        for btn in simulator.CAPABILITIES[EventType.KEY]:
            simulator.emit(EventType.KEY, btn, 1)
            event = next(stream)
            assert event.type == EventType.KEY
            event = next(stream)
            assert event.type == EventType.SYN


@skip(when=not is_uinput_available(), reason="uinput is not available")
@test("device with no capability")
def _(pair_dev_simulator=mouse):
    dev, simulator = pair_dev_simulator
    with dev:
        with raises(ValueError) as error:
            _ = dev.absolute.x
        assert "device has no 'absolute' capability" in str(error.raised)


@skip(when=not is_uinput_available(), reason="uinput is not available")
@test("async button event")
async def _(pair_dev_simulator=gamepad):
    dev, simulator = pair_dev_simulator
    with dev:
        stream = dev.__aiter__()
        for btn in simulator.CAPABILITIES[EventType.KEY]:
            simulator.emit(EventType.KEY, btn, 1)
            event = await stream.__anext__()
            assert event.type == EventType.KEY
            event = await stream.__anext__()
            assert event.type == EventType.SYN


@skip(when=not is_uinput_available(), reason="uinput is not available")
@test("async event batch stream")
async def _(pair_dev_simulator=gamepad):
    dev, simulator = pair_dev_simulator
    with dev:
        stream = async_event_batch_stream(dev.fileno())
        simulator.emit(EventType.KEY, Key.BTN_GAMEPAD, 1)
        batch = await stream.__anext__()
        assert len(batch) == 1
        event = batch[0]
        assert event.type == EventType.KEY
        assert event.code == Key.BTN_GAMEPAD
