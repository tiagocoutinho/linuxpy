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

import pytest
import pytest_asyncio

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


@pytest_asyncio.fixture
async def gamepad():
    name = uuid.uuid4().hex
    with wait_for_new_device() as device_finder:
        with UGamepad(name=name) as simulator:
            assert not simulator.closed
            device = await device_finder()
            yield device, simulator


@pytest_asyncio.fixture
async def mouse():
    name = uuid.uuid4().hex
    with wait_for_new_device() as device_finder:
        with UMouse(name=name) as simulator:
            assert not simulator.closed
            device = await device_finder()
            yield device, simulator


@pytest.mark.asyncio
@pytest.mark.skipif(not is_uinput_available(), reason="uinput is not available")
async def test_find_gamepad():
    name = uuid.uuid4().hex
    with wait_for_new_device() as device_finder:
        with UGamepad(name=name) as simulator:
            await device_finder()
            device = find_gamepad(name=name)
            caps = device.capabilities
            del caps[EventType.SYN]
            assert device.name == simulator.name
            assert caps == simulator.CAPABILITIES


@pytest.mark.asyncio
async def test_find_mouse():
    name = uuid.uuid4().hex
    with wait_for_new_device() as device_finder:
        with UMouse(name=name) as simulator:
            await device_finder()
            device = find_mouse(name=name)
            caps = device.capabilities
            del caps[EventType.SYN]
            assert device.name == simulator.name
            assert caps == simulator.CAPABILITIES


@pytest.mark.skipif(not is_uinput_available(), reason="uinput is not available")
def test_open_close(gamepad):
    dev, _ = gamepad
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


@pytest.mark.skipif(not is_uinput_available(), reason="uinput is not available")
def test_properties(gamepad):
    device, simulator = gamepad
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


@pytest.mark.skipif(not is_uinput_available(), reason="uinput is not available")
def test_grab(gamepad):
    device, simulator = gamepad
    with device:
        with Grab(device):
            assert device.device_id.bustype == simulator.bustype

        device.grab()
        assert device.device_id.bustype == simulator.bustype
        device.ungrab()

        with Grab(device):
            with pytest.raises(OSError):
                device.grab()


@pytest.mark.skipif(not is_uinput_available(), reason="uinput is not available")
def test_button_event(gamepad):
    dev, simulator = gamepad
    with dev:
        stream = iter(dev)
        for btn in simulator.CAPABILITIES[EventType.KEY]:
            simulator.emit(EventType.KEY, btn, 1)
            event = next(stream)
            assert event.type == EventType.KEY
            event = next(stream)
            assert event.type == EventType.SYN


@pytest.mark.skipif(not is_uinput_available(), reason="uinput is not available")
def test_device_with_no_capability(mouse):
    dev, simulator = mouse
    with dev:
        with pytest.raises(ValueError) as error:
            _ = dev.absolute.x
        assert "device has no 'absolute' capability" in str(error.value)


@pytest.mark.asyncio
@pytest.mark.skipif(not is_uinput_available(), reason="uinput is not available")
async def test_async_button_event(gamepad):
    dev, simulator = gamepad
    with dev:
        stream = dev.__aiter__()
        for btn in simulator.CAPABILITIES[EventType.KEY]:
            simulator.emit(EventType.KEY, btn, 1)
            event = await stream.__anext__()
            assert event.type == EventType.KEY
            event = await stream.__anext__()
            assert event.type == EventType.SYN


@pytest.mark.asyncio
@pytest.mark.skipif(not is_uinput_available(), reason="uinput is not available")
async def test_async_event_batch_stream(gamepad):
    dev, simulator = gamepad
    with dev:
        stream = async_event_batch_stream(dev.fileno())
        simulator.emit(EventType.KEY, Key.BTN_GAMEPAD, 1)
        batch = await stream.__anext__()
        assert len(batch) == 1
        event = batch[0]
        assert event.type == EventType.KEY
        assert event.code == Key.BTN_GAMEPAD
