#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Directly compiles the resources.qrc file into resources.py
using PyQt5's built-in functionality rather than calling the external pyrcc5 tool.
"""

import os
import sys
from pathlib import Path

def compile_resources_direct():
    """
    Compiles resources.qrc into resources.py directly using PyQt5.
    """
    # Get paths
    script_dir = Path(__file__).parent
    qrc_file = script_dir / "resources.qrc"
    py_file = script_dir / "resources.py"
    
    # Check if resources.qrc exists
    if not qrc_file.exists():
        print(f"Error: {qrc_file} not found!")
        return False
    
    try:
        from PyQt5.pyrcc_main import processResourceFile
        
        print(f"Compiling {qrc_file} to {py_file}...")
        
        # Open the output file
        with open(py_file, 'w') as out_file:
            # Process the resource file
            processResourceFile([str(qrc_file)], out_file, False)
            
        print(f"Successfully compiled resources to {py_file}")
        return True
    except ImportError:
        print("Error: Could not import PyQt5.pyrcc_main")
        return False
    except Exception as e:
        print(f"Error compiling resources: {e}")
        return False

if __name__ == "__main__":
    compile_resources_direct() 