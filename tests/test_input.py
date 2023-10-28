import asyncio
import pathlib
import uuid
from contextlib import contextmanager

from ward import each, fixture, skip, test

from linuxpy.input.device import (
    Device,
    EventType,
    UGamepad,
    UMouse,
    find_gamepads,
    find_mice,
    is_uinput_available,
)


@contextmanager
def wait_for_new_device():
    base_dir = pathlib.Path("/dev/input")
    assert base_dir.is_dir()
    before = set(base_dir.glob("event*"))

    async def wait():
        while True:
            await asyncio.sleep(0.1)
            new = set(base_dir.glob("event*")) - before
            if new:
                assert len(new) == 1
                filename = new.pop()
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


@skip(when=not is_uinput_available(), reason="uinput is not available")
@test("find device")
async def _(find=each(find_gamepads, find_mice), uclass=each(UGamepad, UMouse)):
    name = uuid.uuid4().hex
    with wait_for_new_device() as device_finder:
        with uclass(name=name) as simulator:
            await device_finder()
            devices = list(find())
            assert devices
            devs = []
            for device in devices:
                with device:
                    if device.name == name:
                        devs.append(device)
            assert len(devs) == 1
            device = devs[0]
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
