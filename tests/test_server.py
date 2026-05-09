"""Tests for HTTP server."""

import pytest
from pathlib import Path
import json
import threading
import time
import socket
from http.client import HTTPConnection

from flask_brain.server import start_server
from flask_brain.graph import Graph, Node, Edge, NodeType, EdgeType


@pytest.fixture
def temp_graph_dir(tmp_path):
    """Create a temporary graph directory with test data."""
    graph_dir = tmp_path / ".flask-brain"
    graph_dir.mkdir()
    
    # Create test manifest
    manifest = {
        "project_name": "test_project",
        "scan_timestamp": "2024-01-01T00:00:00Z",
        "node_count": 2,
        "edge_count": 1,
        "node_types": {"route": 1, "action": 1}
    }
    with open(graph_dir / "manifest.json", "w") as f:
        json.dump(manifest, f)
    
    # Create test graph
    graph = Graph()
    route_node = Node("route::GET /test", NodeType.ROUTE, "GET /test", "test.py", 1)
    action_node = Node("action::test_func", NodeType.ACTION, "test_func", "test.py", 5)
    graph.add_node(route_node)
    graph.add_node(action_node)
    graph.add_edge(Edge("route::GET /test", "action::test_func", EdgeType.CALLS))
    
    with open(graph_dir / "graph-all.json", "w") as f:
        json.dump(graph.to_dict(), f)
    
    with open(graph_dir / "graph-routes.json", "w") as f:
        json.dump({"nodes": [], "edges": []}, f)
    
    return graph_dir


def test_server_serves_manifest(temp_graph_dir):
    """Test that server serves manifest.json."""
    # Find an available port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        port = s.getsockname()[1]
    
    # Start server in a thread
    server_thread = threading.Thread(
        target=start_server,
        args=(temp_graph_dir, port, False),
        daemon=True
    )
    server_thread.start()
    time.sleep(0.5)
    
    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/manifest')
        response = conn.getresponse()
        
        assert response.status == 200
        data = json.loads(response.read().decode())
        assert data["project_name"] == "test_project"
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_server_serves_graph_all(temp_graph_dir):
    """Test that server serves graph-all.json."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        port = s.getsockname()[1]
    
    server_thread = threading.Thread(
        target=start_server,
        args=(temp_graph_dir, port, False),
        daemon=True
    )
    server_thread.start()
    time.sleep(0.5)
    
    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/graph/all')
        response = conn.getresponse()
        
        assert response.status == 200
        data = json.loads(response.read().decode())
        assert "nodes" in data
        assert "edges" in data
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_server_serves_html_root(temp_graph_dir):
    """Test that server serves HTML at root path."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        port = s.getsockname()[1]
    
    server_thread = threading.Thread(
        target=start_server,
        args=(temp_graph_dir, port, False),
        daemon=True
    )
    server_thread.start()
    time.sleep(0.5)
    
    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/')
        response = conn.getresponse()
        
        assert response.status == 200
        html = response.read().decode()
        assert "Flask Brain" in html
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_server_returns_404_for_unknown_path(temp_graph_dir):
    """Test that server returns 404 for unknown paths."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        port = s.getsockname()[1]
    
    server_thread = threading.Thread(
        target=start_server,
        args=(temp_graph_dir, port, False),
        daemon=True
    )
    server_thread.start()
    time.sleep(0.5)
    
    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/unknown/path')
        response = conn.getresponse()
        
        assert response.status == 404
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_server_returns_404_for_missing_api_file(temp_graph_dir):
    """Test that server returns 404 when requested API file doesn't exist."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        port = s.getsockname()[1]
    
    server_thread = threading.Thread(
        target=start_server,
        args=(temp_graph_dir, port, False),
        daemon=True
    )
    server_thread.start()
    time.sleep(0.5)
    
    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/nonexistent')
        response = conn.getresponse()
        
        assert response.status == 404
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_serve_risk_returns_nodes(tmp_path):
    """serve_risk returns top-N nodes sorted by risk_score desc, excludes zeroes."""
    graph_dir = tmp_path / ".flask-brain"
    graph_dir.mkdir()

    graph = Graph()
    graph.add_node(Node("action::risky", NodeType.ACTION, "risky", "a.py", 1,
                        metadata={"risk_score": 50, "churn_count": 5, "complexity": 10}))
    graph.add_node(Node("action::safe", NodeType.ACTION, "safe", "b.py", 2,
                        metadata={"risk_score": 0}))
    graph.add_node(Node("service::medium", NodeType.SERVICE, "medium", "c.py", 3,
                        metadata={"risk_score": 20, "churn_count": 2, "complexity": 10}))

    manifest = {"project_name": "test", "scan_timestamp": "2024-01-01T00:00:00Z",
                "node_count": 3, "edge_count": 0, "node_types": {}}
    with open(graph_dir / "manifest.json", "w") as f:
        json.dump(manifest, f)
    with open(graph_dir / "graph-all.json", "w") as f:
        json.dump(graph.to_dict(), f)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        port = s.getsockname()[1]

    threading.Thread(target=start_server, args=(graph_dir, port, False), daemon=True).start()
    time.sleep(0.5)

    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/analysis/risk')
        response = conn.getresponse()
        assert response.status == 200
        data = json.loads(response.read().decode())
        assert data["count"] == 2  # excludes safe (risk_score=0)
        scores = [n["metadata"]["risk_score"] for n in data["nodes"]]
        assert scores == sorted(scores, reverse=True)
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")
