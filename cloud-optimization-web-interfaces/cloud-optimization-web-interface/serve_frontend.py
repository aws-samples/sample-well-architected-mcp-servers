#!/usr/bin/env python3

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

"""
Simple HTTP server to serve the frontend for local testing
"""

import http.server
import socketserver
import threading
import time
import webbrowser
from pathlib import Path


def serve_frontend(port=8080):
    """Serve the frontend on the specified port"""

    # Change to frontend directory
    frontend_dir = Path(__file__).parent / "frontend"

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(frontend_dir), **kwargs)

        def end_headers(self):
            # Add CORS headers
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            super().end_headers()

    with socketserver.TCPServer(("", port), Handler) as httpd:
        print(f"🌐 Serving frontend at http://localhost:{port}")
        print(f"📁 Frontend directory: {frontend_dir}")
        print(f"🧪 Local test page: http://localhost:{port}/local-test.html")
        print("Press Ctrl+C to stop")

        # Open browser after a short delay
        def open_browser():
            time.sleep(1)
            webbrowser.open(f"http://localhost:{port}/local-test.html")

        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Stopping frontend server...")
            httpd.shutdown()


if __name__ == "__main__":
    serve_frontend()
