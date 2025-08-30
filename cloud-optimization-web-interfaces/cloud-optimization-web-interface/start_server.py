# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#!/usr/bin/env python3
"""
Startup script for the Cloud Optimization MCP Web Interface
"""

import os
import sys
import subprocess
import time
import webbrowser
from pathlib import Path


def install_requirements():
    """Install Python requirements"""
    print("📦 Installing Python requirements...")
    requirements_path = Path(__file__).parent / "backend" / "requirements.txt"

    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements_path)],
            check=True,
            capture_output=True,
        )
        print("✅ Requirements installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install requirements: {e}")
        print("Please install manually with: pip install -r backend/requirements.txt")
        return False

    return True


def start_backend():
    """Start the FastAPI backend server"""
    print("🚀 Starting FastAPI backend server...")

    backend_dir = Path(__file__).parent / "backend"
    os.chdir(backend_dir)

    # Add backend directory to Python path
    sys.path.insert(0, str(backend_dir))

    try:
        # Import and run the FastAPI app
        import uvicorn
        from main import app

        # Start server in a separate process
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info", access_log=True)

    except ImportError as e:
        print(f"❌ Failed to import required modules: {e}")
        print("Please ensure all requirements are installed")
        return False
    except Exception as e:
        print(f"❌ Failed to start backend server: {e}")
        return False


def open_frontend():
    """Open the frontend in the default browser"""
    frontend_path = Path(__file__).parent / "frontend" / "index.html"
    frontend_url = f"file://{frontend_path.absolute()}"

    print(f"🌐 Opening frontend at: {frontend_url}")

    try:
        webbrowser.open(frontend_url)
        print("✅ Frontend opened in browser")
    except Exception as e:
        print(f"❌ Failed to open browser: {e}")
        print(f"Please manually open: {frontend_url}")


def main():
    """Main startup function"""
    print("☁️  AWS Cloud Optimization MCP Web Interface")
    print("=" * 50)

    # Install requirements
    if not install_requirements():
        sys.exit(1)

    print("\n📋 Starting services...")
    print("Backend API: http://localhost:8000")
    print("WebSocket: ws://localhost:8000/ws/{session_id}")
    print("Health Check: http://localhost:8000/health")
    print("API Docs: http://localhost:8000/docs")

    # Open frontend after a short delay
    import threading

    def delayed_frontend_open():
        time.sleep(3)  # Wait for backend to start
        open_frontend()

    frontend_thread = threading.Thread(target=delayed_frontend_open)
    frontend_thread.daemon = True
    frontend_thread.start()

    # Start backend (this will block)
    start_backend()


if __name__ == "__main__":
    main()
