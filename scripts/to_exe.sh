#!/usr/bin/env bash
pyinstaller --onefile src/__init__.py -n datatree --additional-hooks-dir=hooks --add-data "src/data/Packages.zip;data/"