#!/bin/bash
# Script to run Python files with QGIS's Python interpreter

QGIS_PYTHON="/Applications/QGIS.app/Contents/MacOS/bin/python3"
SCRIPT_PATH="$1"

if [ -z "$SCRIPT_PATH" ]; then
    echo "Usage: ./run_qgis.sh <path-to-python-script>"
    exit 1
fi

if [ ! -f "$SCRIPT_PATH" ]; then
    echo "Error: Script file '$SCRIPT_PATH' not found."
    exit 1
fi

echo "Running $SCRIPT_PATH with QGIS Python..."
"$QGIS_PYTHON" "$SCRIPT_PATH" 