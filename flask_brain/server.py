"""HTTP server for Flask Brain viewer."""

import json
import webbrowser
import mimetypes
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import threading


class FlaskBrainHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for Flask Brain."""
    
    def __init__(self, *args, graph_dir: Path = None, viewer_dir: Path = None, **kwargs):
        self.graph_dir = graph_dir or Path.cwd() / ".flask-brain"
        self.viewer_dir = viewer_dir or Path(__file__).parent / "viewer" / "dist"
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # Serve API endpoints
        if path.startswith("/api/"):
            self.serve_api(path, parsed_path.query)
        # Serve static assets
        elif path.startswith("/assets/"):
            self.serve_static(path)
        # Serve root HTML or SPA routes
        elif path == "/" or path == "/index.html" or not "." in path.split("/")[-1]:
            self.serve_html()
        else:
            self.serve_static(path)
    
    def serve_api(self, path: str, query: str):
        """Serve API endpoints."""
        if path == "/api/graph/all":
            self.serve_json_file("graph-all.json")
        elif path == "/api/graph/routes":
            self.serve_json_file("graph-routes.json")
        elif path == "/api/manifest":
            self.serve_json_file("manifest.json")
        else:
            self.send_error(404, "API endpoint not found")
    
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


def create_handler(graph_dir: Path, viewer_dir: Path = None):
    """Create a handler with the graph directory bound."""
    if viewer_dir is None:
        viewer_dir = Path(__file__).parent / "viewer" / "dist"
    
    class BoundHandler(FlaskBrainHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, graph_dir=graph_dir, viewer_dir=viewer_dir, **kwargs)
    return BoundHandler


def start_server(graph_dir: Path, port: int = 7891, open_browser: bool = True):
    """Start the HTTP server."""
    handler = create_handler(graph_dir)
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
