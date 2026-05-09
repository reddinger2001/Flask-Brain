"""HTTP server for Flask Brain viewer."""

import json
import webbrowser
import mimetypes
import subprocess
import sys
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
import threading
from flask_brain.context_export import export_context
from flask_brain.graph import Graph

# ── SSE subscriber registry ──────────────────────────────────────────────────
# Each entry is a threading.Event + queue-like list for SSE messages.
# Keyed by subscriber id; handlers register themselves and deregister on disconnect.
_sse_subscribers: dict = {}
_sse_lock = threading.Lock()


def _register_subscriber(sub_id: str) -> list:
    """Register an SSE subscriber. Returns the message queue (list)."""
    q: list = []
    with _sse_lock:
        _sse_subscribers[sub_id] = q
    return q


def _deregister_subscriber(sub_id: str):
    with _sse_lock:
        _sse_subscribers.pop(sub_id, None)


def broadcast_event(event: str, data: dict):
    """Broadcast an SSE event to all connected subscribers."""
    payload = f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()
    with _sse_lock:
        queues = list(_sse_subscribers.values())
    for q in queues:
        q.append(payload)


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
        elif path == "/api/analysis/dead-weight":
            self.serve_dead_weight()
        elif path == "/api/analysis/blind-spots":
            self.serve_blind_spots()
        elif path == "/api/analysis/impact":
            node_id = params.get("nodeId", [None])[0]
            depth = int(params.get("depth", [5])[0])
            self.serve_impact(node_id, depth)
        elif path == "/api/search":
            query = params.get("q", [""])[0]
            limit = int(params.get("limit", [100])[0])
            self.serve_search(query, limit)
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

    def serve_dead_weight(self):
        """Serve dead-weight analysis: SERVICE/ACTION/TASK nodes with no callers."""
        try:
            graph_path = self.graph_dir / "graph-all.json"
            if not graph_path.exists():
                self._send_json_error(404, "Graph not found — run flask-brain scan first")
                return

            with open(graph_path) as f:
                graph_data = json.load(f)

            graph = Graph.from_dict(graph_data)
            dead_nodes = graph.dead_weight()

            result = {
                "count": len(dead_nodes),
                "nodes": [n.to_dict() for n in dead_nodes],
            }
            self._send_json(result)
        except Exception as e:
            self._send_json_error(500, str(e))

    def serve_search(self, query: str, limit: int = 100):
        """Serve node search results for a query string with predicate support."""
        try:
            graph_path = self.graph_dir / "graph-all.json"
            if not graph_path.exists():
                self._send_json_error(404, "Graph not found — run flask-brain scan first")
                return

            with open(graph_path) as f:
                graph_data = json.load(f)

            graph = Graph.from_dict(graph_data)
            results = graph.search(query, limit=limit)
            self._send_json({
                "query": query,
                "count": len(results),
                "nodes": [n.to_dict() for n in results],
            })
        except Exception as e:
            self._send_json_error(500, str(e))

    def serve_impact(self, node_id: str | None, depth: int = 5):
        """Serve impact analysis: reverse-walk subgraph showing what depends on node_id."""
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
                subgraph = graph.impact_subgraph(node_id, depth=depth)
            except ValueError as e:
                self._send_json_error(404, str(e))
                return

            result = subgraph.to_dict()
            result["root_node_id"] = node_id
            result["depth"] = depth
            self._send_json(result)
        except Exception as e:
            self._send_json_error(500, str(e))

    def serve_blind_spots(self):
        """Serve blind-spot analysis: nodes with DB ops but no resolved model edges."""
        try:
            graph_path = self.graph_dir / "graph-all.json"
            if not graph_path.exists():
                self._send_json_error(404, "Graph not found — run flask-brain scan first")
                return

            with open(graph_path) as f:
                graph_data = json.load(f)

            graph = Graph.from_dict(graph_data)
            blind_nodes = graph.blind_spots()

            result = {
                "count": len(blind_nodes),
                "nodes": [n.to_dict() for n in blind_nodes],
            }
            self._send_json(result)
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
        """Serve Server-Sent Events stream with watch-mode broadcast support."""
        import time
        import uuid
        sub_id = str(uuid.uuid4())
        queue = _register_subscriber(sub_id)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            self.wfile.write(b"retry: 5000\n: connected\n\n")
            self.wfile.flush()
            while True:
                if queue:
                    msg = queue.pop(0)
                    self.wfile.write(msg)
                    self.wfile.flush()
                else:
                    time.sleep(0.25)
                    # Send keepalive ping every ~15 s (60 * 0.25 s)
                    # Using a counter to avoid importing time twice
                    if not hasattr(self, '_ping_counter'):
                        self._ping_counter = 0
                    self._ping_counter += 1
                    if self._ping_counter >= 60:
                        self._ping_counter = 0
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            _deregister_subscriber(sub_id)

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
                 project_path: Path = None, watch: bool = False):
    """Start the HTTP server, optionally with file-watch mode."""
    handler = create_handler(graph_dir, project_path=project_path)
    server = ThreadingHTTPServer(("localhost", port), handler)
    
    url = f"http://localhost:{port}"
    print(f"Flask Brain server running at {url}")
    print(f"Serving graph data from: {graph_dir}")
    if watch:
        print(f"Watch mode enabled — auto-refresh on .py changes (2 s debounce)")
    print("Press Ctrl+C to stop")
    
    if open_browser:
        # Open browser in a separate thread after a short delay
        def open_browser_delayed():
            import time
            time.sleep(1)
            webbrowser.open(url)
        
        threading.Thread(target=open_browser_delayed, daemon=True).start()
    
    # Start watcher if requested
    _watcher = None
    if watch:
        from flask_brain.watcher import ProjectWatcher
        from flask_brain.graph import GraphBuilder

        _proj = project_path or graph_dir.parent

        def _on_change(changed_path: str):
            print(f"[watch] change detected: {changed_path} — rescanning…")
            try:
                builder = GraphBuilder()
                graph = builder.build(_proj)
                graph.write(graph_dir)
                broadcast_event("graph-updated", {"path": changed_path})
                print("[watch] rescan complete — clients notified")
            except Exception as e:
                print(f"[watch] rescan failed: {e}")

        _watcher = ProjectWatcher(_proj, _on_change)
        _watcher.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()
    finally:
        if _watcher is not None:
            _watcher.stop()
