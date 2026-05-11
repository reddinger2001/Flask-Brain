"""Background server entry point.

Invoked by ``flask-brain serve --background`` / ``flask-brain scan --background``
via ``python -m flask_brain._daemon``.  Runs the HTTP server in the foreground
*of the detached subprocess* — the parent process returns immediately after
forking.

Usage (internal — do not call directly):
    python -m flask_brain._daemon <graph_dir> --port 7891 [--project-path /...] [--watch]
"""

import argparse
from pathlib import Path

from flask_brain.server import start_server


def main() -> None:
    parser = argparse.ArgumentParser(prog="flask_brain._daemon", add_help=False)
    parser.add_argument("graph_dir", type=Path)
    parser.add_argument("--port", type=int, default=7891)
    parser.add_argument("--project-path", type=Path, default=None)
    parser.add_argument("--watch", action="store_true", default=False)
    args = parser.parse_args()

    start_server(
        graph_dir=args.graph_dir,
        port=args.port,
        open_browser=False,   # never open browser in daemon mode
        project_path=args.project_path,
        watch=args.watch,
    )


if __name__ == "__main__":
    main()
