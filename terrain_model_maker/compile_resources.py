#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
from pathlib import Path

def compile_resources():
    """
    Compiles the resources.qrc file into resources.py using the pyrcc5 tool.
    This should be run whenever the resources.qrc file is updated.
    """
    qrc_file = Path(__file__).parent / "resources.qrc"
    py_file = Path(__file__).parent / "resources.py"
    
    # Ensure the qrc file exists
    if not qrc_file.exists():
        print(f"Error: {qrc_file} not found!")
        return False
    
    # Use the full path to pyrcc5 in QGIS's installation
    pyrcc5_path = "/Applications/QGIS.app/Contents/MacOS/bin/pyrcc5"
    
    if not os.path.exists(pyrcc5_path):
        print(f"Error: pyrcc5 not found at {pyrcc5_path}")
        # Fall back to using system pyrcc5 if it exists
        try:
            subprocess.run(["which", "pyrcc5"], check=True, capture_output=True)
            pyrcc5_path = "pyrcc5"
            print("Using system pyrcc5 instead")
        except subprocess.CalledProcessError:
            print("Error: pyrcc5 not found in system PATH either")
            return False
    
    try:
        # Run pyrcc5 to compile the resources
        print(f"Running: {pyrcc5_path} -o {str(py_file)} {str(qrc_file)}")
        subprocess.run([pyrcc5_path, "-o", str(py_file), str(qrc_file)], check=True)
        print(f"Successfully compiled resources to {py_file}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error compiling resources: {e}")
        return False
    except FileNotFoundError:
        print("Error: pyrcc5 not found. Make sure PyQt5 is installed and pyrcc5 is in your PATH.")
        return False

if __name__ == "__main__":
    compile_resources() 