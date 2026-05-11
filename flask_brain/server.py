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
            elif path == "/api/generate/tests":
                self.handle_generate_tests()
            else:
                self.send_error(404, "API endpoint not found")
        except BrokenPipeError:
            pass
        except ConnectionResetError:
            pass

    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

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

    def handle_generate_tests(self):
        """Generate pytest scaffolding for a target node."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            params = json.loads(body) if body else {}

            target_id = params.get("target")
            if not target_id:
                self._send_json_error(400, "Missing 'target' parameter")
                return

            graph_path = self.graph_dir / "graph-all.json"
            if not graph_path.exists():
                self._send_json_error(404, "Graph not found — run flask-brain scan first")
                return

            with open(graph_path) as f:
                graph_data = json.load(f)

            graph = Graph.from_dict(graph_data)

            # debug=true: return raw node metadata for every route in scope so callers
            # can confirm what the generator actually reads before code is emitted.
            if params.get("debug"):
                from flask_brain.graph import NodeType
                target_node = graph.get_node(target_id)
                if not target_node:
                    self._send_json_error(404, f"Node '{target_id}' not found in graph")
                    return
                target_type = target_node.type.value
                if target_type == "blueprint":
                    scope = graph.blueprint_subgraph(target_id)
                    route_nodes = [graph.get_node(r["id"]) for r in scope["routes"]]
                elif target_type == "route":
                    route_nodes = [target_node]
                else:
                    route_nodes = []
                debug_info = [
                    {
                        "id": n.id,
                        "label": n.label,
                        "metadata": n.metadata,
                    }
                    for n in route_nodes if n
                ]
                self._send_json({"debug": True, "target_id": target_id, "routes": debug_info})
                return

            from flask_brain.test_generator import generate_tests
            try:
                result = generate_tests(
                    graph=graph,
                    target_id=target_id,
                    conftest_path=params.get("conftest_path"),
                    output_path=params.get("output_path"),
                )
            except ValueError as e:
                msg = str(e)
                # If node not found, suggest similar IDs to help the caller
                if "not found" in msg:
                    keyword = target_id.split("::")[-1].lower()
                    suggestions = [
                        n.id for n in graph.nodes.values()
                        if keyword in n.id.lower() and n.type.value in ("blueprint", "service", "route")
                    ][:10]
                    self._send_json_error(404, msg, {"suggestions": suggestions})
                else:
                    self._send_json_error(400, msg)
                return
            self._send_json(result)
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
        elif path == "/api/analysis/risk":
            self.serve_risk()
        elif path == "/api/snapshots":
            self.serve_snapshots()
        elif path == "/api/diff":
            baseline_id = params.get("baseline", [None])[0]
            current_id = params.get("current", ["current"])[0]
            self.serve_diff(baseline_id, current_id)
        elif path == "/api/trace/route":
            node_id = params.get("id", [None])[0]
            self.serve_trace_route(node_id)
        elif path == "/api/trace/blueprint":
            node_id = params.get("id", [None])[0]
            self.serve_blueprint_subgraph(node_id)
        elif path == "/api/trace/node":
            node_id = params.get("id", [None])[0]
            self.serve_trace_node(node_id)
        elif path == "/api/locate":
            hint = params.get("hint", [""])[0]
            self.serve_locate(hint)
        elif path == "/api/neighbors":
            node_id = params.get("id", [None])[0]
            depth = int(params.get("depth", [2])[0])
            self.serve_neighbors(node_id, depth)
        elif path == "/api/trace/property":
            name = params.get("name", [""])[0]
            self.serve_trace_property(name)
        elif path == "/api/properties/all":
            self.serve_all_properties()
        else:
            self.send_error(404, "API endpoint not found")
    
    def serve_risk(self):
        """Serve top-N highest-risk nodes sorted by risk_score descending."""
        try:
            graph_path = self.graph_dir / "graph-all.json"
            if not graph_path.exists():
                self._send_json_error(404, "Graph not found — run flask-brain scan first")
                return

            with open(graph_path) as f:
                graph_data = json.load(f)

            graph = Graph.from_dict(graph_data)
            nodes = graph.top_risk(limit=50)

            result = {
                "count": len(nodes),
                "nodes": [n.to_dict() for n in nodes],
            }
            self._send_json(result)
        except Exception as e:
            self._send_json_error(500, str(e))

    def serve_snapshots(self):
        """Serve list of available snapshots."""
        try:
            from flask_brain.diff import SnapshotManager
            sm = SnapshotManager(self.project_path)
            snapshots = sm.list_snapshots()
            self._send_json({"count": len(snapshots), "snapshots": snapshots})
        except Exception as e:
            self._send_json_error(500, str(e))

    def serve_diff(self, baseline_id: str | None, current_id: str = "current"):
        """Serve a graph diff between a baseline snapshot and current (or another snapshot)."""
        if not baseline_id:
            self._send_json_error(400, "Missing 'baseline' parameter")
            return

        try:
            from flask_brain.diff import SnapshotManager, DiffEngine

            sm = SnapshotManager(self.project_path)

            try:
                baseline_graph = sm.load_snapshot(baseline_id)
            except ValueError as e:
                self._send_json_error(404, str(e))
                return

            if current_id == "current":
                graph_path = self.graph_dir / "graph-all.json"
                if not graph_path.exists():
                    self._send_json_error(404, "No current graph — run flask-brain scan first")
                    return
                with open(graph_path) as f:
                    current_graph = Graph.from_dict(json.load(f))
            else:
                try:
                    current_graph = sm.load_snapshot(current_id)
                except ValueError as e:
                    self._send_json_error(404, str(e))
                    return

            diff = DiffEngine().compute_diff(baseline_graph, current_graph, baseline_id, current_id)
            self._send_json(diff.to_dict())
        except Exception as e:
            self._send_json_error(500, str(e))

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

    def serve_trace_route(self, node_id: str | None):
        """Serve execution chain for a route: route → actions → services → models."""
        if not node_id:
            self._send_json_error(400, "Missing 'id' parameter")
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
                result = graph.trace_route(node_id)
            except ValueError as e:
                self._send_json_error(404, str(e))
                return
            self._send_json(result)
        except Exception as e:
            self._send_json_error(500, str(e))

    def serve_blueprint_subgraph(self, node_id: str | None):
        """Serve blueprint subgraph: blueprint → routes → actions → services → models."""
        if not node_id:
            self._send_json_error(400, "Missing 'id' parameter")
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
                result = graph.blueprint_subgraph(node_id)
            except ValueError as e:
                self._send_json_error(404, str(e))
                return
            self._send_json(result)
        except Exception as e:
            self._send_json_error(500, str(e))

    def serve_locate(self, hint: str):
        """Serve feature location: best-fit blueprint and service for a hint string."""
        if not hint:
            self._send_json_error(400, "Missing 'hint' parameter")
            return
        try:
            graph_path = self.graph_dir / "graph-all.json"
            if not graph_path.exists():
                self._send_json_error(404, "Graph not found — run flask-brain scan first")
                return
            with open(graph_path) as f:
                graph_data = json.load(f)
            graph = Graph.from_dict(graph_data)
            result = graph.locate(hint)
            self._send_json(result)
        except Exception as e:
            self._send_json_error(500, str(e))

    def serve_trace_node(self, node_id: str | None):
        """Serve forward+backward trace for any node: callers, callees, models, tasks."""
        if not node_id:
            self._send_json_error(400, "Missing 'id' parameter")
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
                result = graph.trace_node(node_id)
            except ValueError as e:
                self._send_json_error(404, str(e))
                return
            self._send_json(result)
        except Exception as e:
            self._send_json_error(500, str(e))

    def serve_neighbors(self, node_id: str | None, depth: int = 2):
        """Serve bidirectional neighborhood subgraph around a node up to depth hops."""
        if not node_id:
            self._send_json_error(400, "Missing 'id' parameter")
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
                result = graph.neighbors(node_id, depth=depth)
            except ValueError as e:
                self._send_json_error(404, str(e))
                return
            self._send_json(result)
        except Exception as e:
            self._send_json_error(500, str(e))

    def serve_trace_property(self, name: str):
        """Serve property trace: all property nodes matching the query name."""
        if not name:
            self._send_json_error(400, "Missing 'name' parameter")
            return
        try:
            graph_path = self.graph_dir / "graph-all.json"
            if not graph_path.exists():
                self._send_json_error(404, "Graph not found — run flask-brain scan first")
                return
            with open(graph_path) as f:
                graph_data = json.load(f)
            graph = Graph.from_dict(graph_data)
            
            # Find all property nodes matching the name (case-insensitive, partial match)
            query_lower = name.lower()
            matching_nodes = [
                n for n in graph.nodes.values()
                if n.type.value == "property" and query_lower in n.label.lower()
            ]
            
            results = []
            for node in matching_nodes:
                # Find readers and writers
                readers = []
                writers = []
                for edge in graph.edges:
                    if edge.target == node.id:
                        if edge.type.value == "reads_property":
                            source_node = graph.get_node(edge.source)
                            if source_node:
                                readers.append(source_node.label)
                        elif edge.type.value == "writes_property":
                            source_node = graph.get_node(edge.source)
                            if source_node:
                                writers.append(source_node.label)
                
                results.append({
                    "node_id": node.id,
                    "class_name": node.metadata.get("class_name", ""),
                    "prop_name": node.metadata.get("prop_name", ""),
                    "file_path": node.file_path,
                    "has_getter": node.metadata.get("has_getter", False),
                    "has_setter": node.metadata.get("has_setter", False),
                    "has_deleter": node.metadata.get("has_deleter", False),
                    "is_class_var": node.metadata.get("is_class_var", False),
                    "is_instance_var": node.metadata.get("is_instance_var", False),
                    "orphaned_getter": node.metadata.get("orphaned_getter", False),
                    "orphaned_setter": node.metadata.get("orphaned_setter", False),
                    "definitions": node.metadata.get("definitions", []),
                    "reads": node.metadata.get("reads", []),
                    "writes": node.metadata.get("writes", []),
                    "readers": list(set(readers)),
                    "writers": list(set(writers)),
                })
            
            self._send_json({
                "query": name,
                "results": results,
            })
        except Exception as e:
            self._send_json_error(500, str(e))

    def serve_all_properties(self):
        """Serve all property nodes for building search index."""
        try:
            graph_path = self.graph_dir / "graph-all.json"
            if not graph_path.exists():
                self._send_json_error(404, "Graph not found — run flask-brain scan first")
                return
            with open(graph_path) as f:
                graph_data = json.load(f)
            graph = Graph.from_dict(graph_data)
            
            # Get all property nodes
            property_nodes = [
                n.to_dict() for n in graph.nodes.values()
                if n.type.value == "property"
            ]
            
            self._send_json({
                "count": len(property_nodes),
                "properties": property_nodes,
            })
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

    def _send_json_error(self, code: int, message: str, extra: dict | None = None):
        """Send a JSON error response."""
        payload = {"error": message}
        if extra:
            payload.update(extra)
        body = json.dumps(payload).encode()
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
