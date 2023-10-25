import time
import uuid

from ward import skip, test, each, fixture, Scope


from linuxpy.input.device import (
    EventType,
    is_uinput_available,
    UGamepad,
    UMouse,
    find_gamepads,
    find_mice,
)


@fixture
def gamepad():
    name = uuid.uuid4().hex
    with UGamepad(name=name) as simulator:
        assert not simulator.closed
        simulator.open()
        time.sleep(1)
        for pad in find_gamepads():
            with pad:
                name = pad.name
            if pad.name == name:
                yield pad, simulator
                break


@skip(when=not is_uinput_available(), reason="uinput is not available")
@test("find device")
def _(find=each(find_gamepads, find_mice), uclass=each(UGamepad, UMouse)):
    name = uuid.uuid4().hex
    with uclass(name=name) as simulator:
        # give kernel time to expose the device
        time.sleep(10)
        time.sleep(1)
        devices = find()
        devices = list(devices)
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
    dev, simulator = pair_dev_simulator
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
        assert type(device.x) is int
        assert type(device.y) is int
        assert type(device.rx) is int
        assert type(device.ry) is int
        assert type(device.rz) is int
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
