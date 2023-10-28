#!/usr/bin/env bash

set -e
set -x

ruff check --diff --output-format=github linuxpy tests examples
ruff format linuxpy tests examples --check
