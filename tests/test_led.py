#
# This file is part of the linuxpy project
#
# Copyright (c) 2024 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import pathlib
import time

import pytest

from linuxpy.led import LED, LED_PATH, ULED, find, iter_device_paths, iter_devices
from linuxpy.util import random_name

ULED_PREPARED = pathlib.Path(ULED.PATH).exists()


@pytest.fixture
def uled():
    with ULED(f"test::{random_name()}", max_brightness=5) as uled:
        # wait for /etc/udev/rules.d to take effect
        time.sleep(0.01)
        yield uled


@pytest.fixture
def uled_colored():
    with ULED(f"test:red:{random_name()}", max_brightness=5) as uled:
        # wait for /etc/udev/rules.d to take effect
        time.sleep(0.01)
        yield uled


@pytest.fixture
def uled_simple():
    with ULED(random_name(), max_brightness=5) as uled:
        # wait for /etc/udev/rules.d to take effect
        time.sleep(0.01)
        yield uled


@pytest.fixture
def uled_single_colon():
    with ULED(f"red:{random_name()}", max_brightness=5) as uled:
        # wait for /etc/udev/rules.d to take effect
        time.sleep(0.01)
        yield uled


@pytest.mark.skipif(not ULED_PREPARED, reason="uled not prepared")
def test_led_name(uled, uled_colored, uled_simple, uled_single_colon):
    devicename, color, function = uled.name.split(":")
    led = LED.from_name(uled.name)
    assert led.devicename == devicename
    assert led.color == color
    assert led.function == function
    assert led.name == uled.name
    assert led.name == f"{led.devicename}:{led.color}:{led.function}"
    assert repr(led) == f"LED({led.name})"

    devicename, color, function = "", "", uled_simple.name
    led = LED.from_name(uled_simple.name)
    assert led.function == function
    assert led.color == color
    assert led.devicename == devicename
    assert led.name == led.function
    assert led.name == uled_simple.name
    assert repr(led) == f"LED({led.name})"

    devicename, color, function = uled_colored.name.split(":")
    led = LED.from_name(uled_colored.name)
    assert led.color == color
    assert led.devicename == devicename
    assert led.function == function
    assert led.name == f"{led.devicename}:{led.color}:{led.function}"
    assert led.name == uled_colored.name
    assert repr(led) == f"LED({led.name})"

    devicename, color, function = "", *uled_single_colon.name.split(":")
    led = LED.from_name(uled_single_colon.name)
    assert led.color == color
    assert led.devicename == devicename
    assert led.function == function
    assert led.name == f"{led.color}:{led.function}"
    assert led.name == uled_single_colon.name
    assert repr(led) == f"LED({led.name})"


@pytest.mark.skipif(not ULED_PREPARED, reason="uled not prepared")
def test_led_brightness(uled):
    led = LED.from_name(uled.name)
    assert led.brightness == 0
    led.brightness = 1
    assert led.brightness == 1
    assert uled.brightness == 1


@pytest.mark.skipif(not ULED_PREPARED, reason="uled not prepared")
def test_led_trigger(uled):
    led = LED.from_name(uled.name)
    assert led.trigger == "none"
    assert not led.trigger_enabled
    assert led.triggers
    led.trigger = led.triggers[-1]
    assert led.trigger == led.triggers[-1]
    assert led.trigger_enabled


@pytest.mark.skipif(not ULED_PREPARED, reason="uled not prepared")
def test_led_path_list(uled, uled_colored, uled_simple, uled_single_colon):
    paths = list(iter_device_paths())

    assert len(paths) >= 4
    assert LED_PATH / uled.name in paths
    assert LED_PATH / uled_colored.name in paths
    assert LED_PATH / uled_simple.name in paths
    assert LED_PATH / uled_single_colon.name in paths


@pytest.mark.skipif(not ULED_PREPARED, reason="uled not prepared")
def test_led_list(uled, uled_colored, uled_simple, uled_single_colon):
    devs = list(iter_devices())
    paths = [dev.syspath.stem for dev in devs]
    assert uled.name in paths
    assert uled_colored.name in paths
    assert uled_simple.name in paths
    assert uled_single_colon.name in paths


@pytest.mark.skipif(not ULED_PREPARED, reason="uled not prepared")
def test_find_led(uled, uled_colored, uled_simple, uled_single_colon):
    devicename, color, function = uled.name.split(":")
    led = find(function=uled.name.split(":")[-1])
    assert led.devicename == devicename
    assert led.color == color
    assert led.function == function
    assert led.name == uled.name
    assert led.name == f"{led.devicename}:{led.color}:{led.function}"
    assert repr(led) == f"LED({led.name})"

    leds = list(find(find_all=True))
    assert len(leds) >= 4


@pytest.mark.skipif(not ULED_PREPARED, reason="uled not prepared")
def test_led_brightness_events(uled):
    led = LED.from_name(uled.name)
    assert not led.brightness_events_path.exists()


@pytest.mark.skipif(not ULED_PREPARED, reason="uled not prepared")
def test_uled_stream(uled):
    led = LED.from_name(uled.name)
    assert led.brightness == 0
    led.brightness = 1
    stream = uled.stream()
    assert next(stream) == 1
