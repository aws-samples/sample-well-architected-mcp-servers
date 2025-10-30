#!/usr/bin/env python3
"""
Wrapper script to run the AWS API MCP Server with proper import handling.
"""

import os
import sys

# Add the current directory and parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Run the server as a module to handle relative imports
if __name__ == '__main__':
    # Change to the src directory to ensure relative imports work
    os.chdir(current_dir)
    
    # Run the server module using python -m
    import subprocess
    result = subprocess.run([sys.executable, '-m', 'server'], cwd=current_dir)
    sys.exit(result.returncode)