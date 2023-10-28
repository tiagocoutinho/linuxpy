#!/bin/sh -e
set -x

ruff linuxpy tests examples --fix
ruff format linuxpy tests examples
