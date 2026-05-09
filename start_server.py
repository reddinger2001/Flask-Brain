#!/usr/bin/env python3
"""Reliable Flask Brain server startup script."""
from pathlib import Path
from flask_brain.server import start_server

GRAPH_DIR = Path('/Volumes/DevEnvironment/projects/VendorSync/.flask-brain')
PROJECT_PATH = Path('/Volumes/DevEnvironment/projects/VendorSync')
PORT = 7891

print(f"Starting Flask Brain on http://localhost:{PORT}")
print(f"Project: {PROJECT_PATH}")
start_server(GRAPH_DIR, port=PORT, open_browser=False, project_path=PROJECT_PATH)
