"""HTTP server for Flask Brain viewer."""

import json
import webbrowser
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import threading


class FlaskBrainHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for Flask Brain."""
    
    def __init__(self, *args, graph_dir: Path = None, **kwargs):
        self.graph_dir = graph_dir or Path.cwd() / ".flask-brain"
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # Serve API endpoints
        if path.startswith("/api/"):
            self.serve_api(path, parsed_path.query)
        # Serve root HTML
        elif path == "/" or path == "/index.html":
            self.serve_html()
        else:
            self.send_error(404, "Not Found")
    
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
    
    def serve_html(self):
        """Serve the placeholder HTML viewer."""
        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flask Brain - Architecture Visualizer</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            max-width: 1200px;
            width: 100%;
        }
        h1 {
            color: #667eea;
            margin-bottom: 10px;
            font-size: 2.5em;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 1.1em;
        }
        .status {
            background: #f0f9ff;
            border-left: 4px solid #0ea5e9;
            padding: 20px;
            margin: 20px 0;
            border-radius: 8px;
        }
        .status h2 {
            color: #0ea5e9;
            margin-bottom: 10px;
        }
        .graph-data {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            max-height: 500px;
            overflow: auto;
        }
        pre {
            margin: 0;
            font-size: 0.9em;
            line-height: 1.5;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        .stat-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 12px;
            text-align: center;
        }
        .stat-value {
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
        }
        .stat-label {
            opacity: 0.9;
            font-size: 0.9em;
        }
        .footer {
            text-align: center;
            color: #666;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e2e8f0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧠 Flask Brain</h1>
        <p class="subtitle">Interactive Architecture Visualizer</p>
        
        <div class="status">
            <h2>✅ Backend Running</h2>
            <p>Flask Brain backend is successfully running and serving graph data.</p>
            <p><strong>Note:</strong> The React frontend will be built separately. For now, you can view the raw graph data below.</p>
        </div>
        
        <div id="stats" class="stats"></div>
        
        <h2 style="margin: 30px 0 15px 0; color: #334155;">Graph Data</h2>
        <div class="graph-data">
            <pre id="graph-data">Loading graph data...</pre>
        </div>
        
        <div class="footer">
            <p>Flask Brain v0.1.0 | <a href="http://192.168.1.127:3000/Chris/flask-brain" target="_blank">View on Forgejo</a></p>
        </div>
    </div>
    
    <script>
        // Load graph data
        fetch('/api/manifest')
            .then(r => r.json())
            .then(manifest => {
                // Display stats
                const statsHtml = `
                    <div class="stat-card">
                        <div class="stat-label">Total Nodes</div>
                        <div class="stat-value">${manifest.node_count}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Total Edges</div>
                        <div class="stat-value">${manifest.edge_count}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Routes</div>
                        <div class="stat-value">${manifest.node_types.route || 0}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Models</div>
                        <div class="stat-value">${manifest.node_types.model || 0}</div>
                    </div>
                `;
                document.getElementById('stats').innerHTML = statsHtml;
            })
            .catch(err => console.error('Error loading manifest:', err));
        
        fetch('/api/graph/all')
            .then(r => r.json())
            .then(data => {
                document.getElementById('graph-data').textContent = JSON.stringify(data, null, 2);
            })
            .catch(err => {
                document.getElementById('graph-data').textContent = 'Error loading graph data: ' + err.message;
            });
    </script>
</body>
</html>"""
        
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())
    
    def log_message(self, format, *args):
        """Override to reduce logging noise."""
        pass


def create_handler(graph_dir: Path):
    """Create a handler with the graph directory bound."""
    class BoundHandler(FlaskBrainHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, graph_dir=graph_dir, **kwargs)
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
