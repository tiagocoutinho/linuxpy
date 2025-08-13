#
# This file is part of the linuxpy project
#
# Copyright (c) 2025 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import os
from contextlib import ExitStack, contextmanager
from inspect import isgenerator
from pathlib import Path
from random import randint
from unittest import mock

import pytest

from linuxpy.thermal import (
    CoolingDevice,
    ThermalZone,
    iter_cooling_device_paths,
    iter_cooling_devices,
    iter_thermal_zone_devices,
    iter_thermal_zone_paths,
)


class Hardware:
    def __init__(self, filename="/dev/video39"):
        self.filename = filename
        self.fd = None
        self.fobj = None

    def __enter__(self):
        self.stack = ExitStack()
        opener = mock.patch("linuxpy.io.open", self.open)
        blocking = mock.patch("linuxpy.device.os.get_blocking", self.get_blocking)
        self.stack.enter_context(opener)
        self.stack.enter_context(blocking)
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.stack.close()

    def open(self, filename, mode, buffering=-1, opener=None):
        self.fd = randint(100, 1000)
        self.fobj = mock.Mock()
        self.fobj.fileno.return_value = self.fd
        self.fobj.get_blocking.return_value = False
        self.fobj.closed = False
        return self.fobj

    def get_blocking(self, fd):
        assert self.fd == fd
        return self.fobj.get_blocking()


@pytest.fixture
def hardware():
    with Hardware() as hardware:
        yield hardware


@contextmanager
def thermal_files(paths=("/sys/class/thermal/thermal_zone99",)):
    with mock.patch("linuxpy.device.pathlib.Path.glob") as glob:
        expected_files = list(paths)
        glob.return_value = expected_files
        with mock.patch("linuxpy.device.pathlib.Path.is_char_device") as is_char_device:
            is_char_device.return_value = True
            with mock.patch("linuxpy.device.os.access") as access:
                access.return_value = os.R_OK | os.W_OK
                yield paths


def test_thermal_files():
    names = [f"/sys/class/thermal/thermal_zone{id_}" for id_ in (33, 55)]
    with thermal_files(names) as expected_files:
        assert list(iter_thermal_zone_paths()) == expected_files


def test_cooling_files():
    names = [f"/sys/class/thermal/cooling_device{id_}" for id_ in (33, 55)]
    with thermal_files(names) as expected_files:
        assert list(iter_cooling_device_paths()) == expected_files


def test_thermal_device_list():
    assert isgenerator(iter_thermal_zone_devices())
    names = [f"/sys/class/thermal/thermal_zone{id_}" for id_ in (33, 55)]
    with thermal_files(names) as expected_files:
        devices = list(iter_thermal_zone_devices())
        assert len(devices) == 2
        for device in devices:
            assert isinstance(device, ThermalZone)
        assert {device.devpath for device in devices} == {Path(filename) for filename in expected_files}


def test_cooling_device_list():
    assert isgenerator(iter_cooling_devices())
    names = [f"/sys/class/thermal/cooling_device{id_}" for id_ in (33, 55)]
    with thermal_files(names) as expected_files:
        devices = list(iter_cooling_devices())
        assert len(devices) == 2
        for device in devices:
            assert isinstance(device, CoolingDevice)
        assert {device.devpath for device in devices} == {Path(filename) for filename in expected_files}
