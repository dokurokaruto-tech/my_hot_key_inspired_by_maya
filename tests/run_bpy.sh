#!/bin/bash
# Run a Python script inside the headless Blender 5.2.0 (PyPI bpy wheel) environment.
# Usage: run_bpy.sh <script.py> [args...]
export LD_LIBRARY_PATH=/home/user/build/xstub
export PYTHONPATH=/home/user/build/py313/site
exec /home/user/build/py313/bin/python3 "$@"
