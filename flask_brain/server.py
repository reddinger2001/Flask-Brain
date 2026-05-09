"""HTTP server for Flask Brain viewer."""

import json
import webbrowser
import mimetypes
import subprocess
import sys
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import threading
from flask_brain.context_export import export_context
from flask_brain.graph import Graph


class FlaskBrainHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for Flask Brain."""

    def __init__(self, *args, graph_dir: Path = None, viewer_dir: Path = None,
                 project_path: Path = None, **kwargs):
        self.graph_dir = graph_dir or Path.cwd() / ".flask-brain"
        self.viewer_dir = viewer_dir or Path(__file__).parent / "viewer" / "dist"
        self.project_path = project_path or Path.cwd()
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Handle GET requests."""
        try:
            parsed_path = urlparse(self.path)
            path = parsed_path.path

            if path.startswith("/api/"):
                self.serve_api(path, parsed_path.query)
            elif path.startswith("/assets/"):
                self.serve_static(path)
            elif path == "/" or path == "/index.html" or "." not in path.split("/")[-1]:
                self.serve_html()
            else:
                self.serve_static(path)
        except BrokenPipeError:
            pass
        except ConnectionResetError:
            pass

    def do_POST(self):
        """Handle POST requests."""
        try:
            parsed_path = urlparse(self.path)
            path = parsed_path.path

            if path == "/api/scan":
                self.handle_rescan()
            else:
                self.send_error(404, "API endpoint not found")
        except BrokenPipeError:
            pass
        except ConnectionResetError:
            pass

    def handle_rescan(self):
        """Trigger a rescan of the project."""
        try:
            from flask_brain.graph import GraphBuilder
            builder = GraphBuilder()
            graph = builder.build(self.project_path)
            graph.write(self.graph_dir)

            manifest_path = self.graph_dir / "manifest.json"
            with open(manifest_path) as f:
                manifest = json.load(f)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(manifest).encode())
        except Exception as e:
            self._send_json_error(500, str(e))

    def serve_api(self, path: str, query: str):
        """Serve API endpoints."""
        params = parse_qs(query)

        if path == "/api/manifest":
            self.serve_json_file("manifest.json")
        elif path == "/api/graph/all":
            self.serve_json_file("graph-all.json")
        elif path == "/api/graph/routes":
            self.serve_json_file("graph-routes.json")
        elif path.startswith("/api/graph/"):
            # Per-route subgraph: /api/graph/<safe-route-id>
            route_id = path[len("/api/graph/"):]
            self.serve_json_file(f"graph-{route_id}.json")
        elif path == "/api/source":
            file_path = params.get("path", [None])[0]
            line = params.get("line", [1])[0]
            self.serve_source(file_path, int(line))
        elif path == "/api/context":
            node_id = params.get("nodeId", [None])[0]
            self.serve_context(node_id)
        elif path == "/api/events":
            self.serve_sse()
        else:
            self.send_error(404, "API endpoint not found")
    
    def serve_source(self, file_path: str, line: int):
        """Serve source file content."""
        if not file_path:
            self._send_json_error(400, "Missing 'path' parameter")
            return

        full_path = self.project_path / file_path
        if not full_path.exists() or not full_path.is_file():
            self._send_json_error(404, f"File not found: {file_path}")
            return

        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
            response = {"content": content, "path": file_path, "line": line}
            self._send_json(response)
        except Exception as e:
            self._send_json_error(500, str(e))

    def serve_context(self, node_id: str):
        """Serve AI context export for a node using context_export.py."""
        if not node_id:
            self._send_json_error(400, "Missing 'nodeId' parameter")
            return

        try:
            graph_path = self.graph_dir / "graph-all.json"
            if not graph_path.exists():
                self._send_json_error(404, "Graph not found — run flask-brain scan first")
                return

            with open(graph_path) as f:
                graph_data = json.load(f)

            graph = Graph.from_dict(graph_data)

            try:
                context_md = export_context(graph, node_id)
            except ValueError as e:
                self._send_json_error(404, str(e))
                return

            self._send_json({"context": context_md, "node_id": node_id})
        except Exception as e:
            self._send_json_error(500, str(e))

    def serve_sse(self):
        """Serve Server-Sent Events stream — sends keepalives, no watch mode yet."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        # Tell the browser not to retry aggressively (retry: 0 disables auto-reconnect)
        self.end_headers()
        try:
            # Send a comment ping every 15 s to keep the connection alive.
            # The browser will hold one open connection and stop hammering us.
            self.wfile.write(b"retry: 0\n: connected\n\n")
            self.wfile.flush()
            import time
            while True:
                time.sleep(15)
                self.wfile.write(b": ping\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _send_json(self, data: dict):
        """Send a JSON response."""
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json_error(self, code: int, message: str):
        """Send a JSON error response."""
        body = json.dumps({"error": message}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_json_file(self, filename: str):
        """Serve a JSON file from the graph directory."""
        file_path = self.graph_dir / filename
        if not file_path.exists():
            self.send_error(404, f"File not found: {filename}")
            return
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        except Exception as e:
            self.send_error(500, f"Error reading file: {str(e)}")
    
    def serve_static(self, path: str):
        """Serve static files from the viewer dist directory."""
        # Remove leading slash
        file_path = self.viewer_dir / path.lstrip("/")
        
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, f"File not found: {path}")
            return
        
        try:
            # Determine content type
            content_type, _ = mimetypes.guess_type(str(file_path))
            if content_type is None:
                content_type = "application/octet-stream"
            
            with open(file_path, 'rb') as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error reading file: {str(e)}")
    
    def serve_html(self):
        """Serve the React SPA index.html."""
        index_path = self.viewer_dir / "index.html"
        
        if not index_path.exists():
            self.send_error(500, "React app not built. Run 'npm run build' in frontend/")
            return
        
        try:
            with open(index_path, 'rb') as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error reading index.html: {str(e)}")
    
    def log_message(self, format, *args):
        """Override to reduce logging noise."""
        pass


def create_handler(graph_dir: Path, viewer_dir: Path = None, project_path: Path = None):
    """Create a handler with the graph directory bound."""
    if viewer_dir is None:
        viewer_dir = Path(__file__).parent / "viewer" / "dist"
    if project_path is None:
        project_path = graph_dir.parent

    class BoundHandler(FlaskBrainHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(
                *args,
                graph_dir=graph_dir,
                viewer_dir=viewer_dir,
                project_path=project_path,
                **kwargs,
            )
    return BoundHandler


def start_server(graph_dir: Path, port: int = 7891, open_browser: bool = True,
                 project_path: Path = None):
    """Start the HTTP server."""
    handler = create_handler(graph_dir, project_path=project_path)
    server = HTTPServer(("localhost", port), handler)
    
    url = f"http://localhost:{port}"
    print(f"Flask Brain server running at {url}")
    print(f"Serving graph data from: {graph_dir}")
    print("Press Ctrl+C to stop")
    
    if open_browser:
        # Open browser in a separate thread after a short delay
        def open_browser_delayed():
            import time
            time.sleep(1)
            webbrowser.open(url)
        
        threading.Thread(target=open_browser_delayed, daemon=True).start()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()
