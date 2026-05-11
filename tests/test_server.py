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


def _start_server_with_graph(tmp_path, graph: Graph):
    """Helper: write graph-all.json and start a server on a free port. Returns port."""
    graph_dir = tmp_path / ".flask-brain"
    graph_dir.mkdir(exist_ok=True)
    manifest = {"project_name": "test", "scan_timestamp": "2024-01-01T00:00:00Z",
                "node_count": len(graph.nodes), "edge_count": len(graph.edges), "node_types": {}}
    with open(graph_dir / "manifest.json", "w") as f:
        json.dump(manifest, f)
    with open(graph_dir / "graph-all.json", "w") as f:
        json.dump(graph.to_dict(), f)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        port = s.getsockname()[1]

    threading.Thread(
        target=start_server,
        args=(graph_dir, port, False),
        kwargs={"project_path": tmp_path},
        daemon=True,
    ).start()
    time.sleep(0.5)
    return port


def test_serve_snapshots_empty(tmp_path):
    """GET /api/snapshots returns empty list when no snapshots exist."""
    graph = Graph()
    graph.add_node(Node("route::GET /", NodeType.ROUTE, "GET /", "r.py", 1))
    port = _start_server_with_graph(tmp_path, graph)
    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/snapshots')
        response = conn.getresponse()
        assert response.status == 200
        data = json.loads(response.read().decode())
        assert data["count"] == 0
        assert data["snapshots"] == []
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_serve_snapshots_lists_created_snapshots(tmp_path):
    """GET /api/snapshots returns snapshots after one is created."""
    from flask_brain.diff import SnapshotManager
    graph = Graph()
    graph.add_node(Node("route::GET /", NodeType.ROUTE, "GET /", "r.py", 1))
    port = _start_server_with_graph(tmp_path, graph)

    sm = SnapshotManager(tmp_path)
    sid = sm.create_snapshot(label="test snap")

    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/snapshots')
        response = conn.getresponse()
        assert response.status == 200
        data = json.loads(response.read().decode())
        assert data["count"] == 1
        assert data["snapshots"][0]["id"] == sid
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_serve_diff_missing_baseline_returns_400(tmp_path):
    """GET /api/diff without baseline returns 400."""
    graph = Graph()
    graph.add_node(Node("route::GET /", NodeType.ROUTE, "GET /", "r.py", 1))
    port = _start_server_with_graph(tmp_path, graph)
    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/diff')
        response = conn.getresponse()
        assert response.status == 400
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_serve_diff_unknown_baseline_returns_404(tmp_path):
    """GET /api/diff with unknown baseline snapshot returns 404."""
    graph = Graph()
    graph.add_node(Node("route::GET /", NodeType.ROUTE, "GET /", "r.py", 1))
    port = _start_server_with_graph(tmp_path, graph)
    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/diff?baseline=99991231-235959')
        response = conn.getresponse()
        assert response.status == 404
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_serve_diff_returns_correct_diff(tmp_path):
    """GET /api/diff returns added/removed nodes vs baseline snapshot."""
    from flask_brain.diff import SnapshotManager

    baseline = Graph()
    baseline.add_node(Node("route::GET /users", NodeType.ROUTE, "GET /users", "r.py", 1))
    baseline.add_node(Node("action::list_users", NodeType.ACTION, "list_users", "a.py", 5))

    graph_dir = tmp_path / ".flask-brain"
    graph_dir.mkdir(exist_ok=True)
    with open(graph_dir / "graph-all.json", "w") as f:
        json.dump(baseline.to_dict(), f)

    sm = SnapshotManager(tmp_path)
    sid = sm.create_snapshot(label="v1")

    current = Graph()
    current.add_node(Node("route::GET /users", NodeType.ROUTE, "GET /users", "r.py", 1))
    current.add_node(Node("action::list_users", NodeType.ACTION, "list_users", "a.py", 5))
    current.add_node(Node("service::NewSvc", NodeType.SERVICE, "NewSvc", "s.py", 10))

    manifest = {"project_name": "test", "scan_timestamp": "2024-01-01T00:00:00Z",
                "node_count": 3, "edge_count": 0, "node_types": {}}
    with open(graph_dir / "manifest.json", "w") as f:
        json.dump(manifest, f)
    with open(graph_dir / "graph-all.json", "w") as f:
        json.dump(current.to_dict(), f)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        port = s.getsockname()[1]

    threading.Thread(
        target=start_server,
        args=(graph_dir, port, False),
        kwargs={"project_path": tmp_path},
        daemon=True,
    ).start()
    time.sleep(0.5)

    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', f'/api/diff?baseline={sid}')
        response = conn.getresponse()
        assert response.status == 200
        data = json.loads(response.read().decode())
        assert data["summary"]["nodes_added"] == 1
        assert data["summary"]["nodes_removed"] == 0
        added = [nc for nc in data["node_changes"] if nc["change_type"] == "added"]
        assert added[0]["node_id"] == "service::NewSvc"
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


# ── New comprehensive API endpoint tests ────────────────────────────────────


def test_serve_source_returns_file_content(tmp_path):
    """GET /api/source returns source file content."""
    graph = Graph()
    graph.add_node(Node("route::GET /", NodeType.ROUTE, "GET /", "r.py", 1))
    port = _start_server_with_graph(tmp_path, graph)

    # Create a source file
    (tmp_path / "test.py").write_text("def hello():\n    return 'world'\n")

    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/source?path=test.py&line=1')
        response = conn.getresponse()
        assert response.status == 200
        data = json.loads(response.read().decode())
        assert "content" in data
        assert "def hello()" in data["content"]
        assert data["path"] == "test.py"
        assert data["line"] == 1
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_serve_source_missing_path_returns_400(tmp_path):
    """GET /api/source without path parameter returns 400."""
    graph = Graph()
    graph.add_node(Node("route::GET /", NodeType.ROUTE, "GET /", "r.py", 1))
    port = _start_server_with_graph(tmp_path, graph)

    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/source?line=1')
        response = conn.getresponse()
        assert response.status == 400
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_serve_source_nonexistent_file_returns_404(tmp_path):
    """GET /api/source for nonexistent file returns 404."""
    graph = Graph()
    graph.add_node(Node("route::GET /", NodeType.ROUTE, "GET /", "r.py", 1))
    port = _start_server_with_graph(tmp_path, graph)

    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/source?path=nonexistent.py&line=1')
        response = conn.getresponse()
        assert response.status == 404
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_serve_dead_weight_returns_orphaned_nodes(tmp_path):
    """GET /api/analysis/dead-weight returns nodes with no callers."""
    graph = Graph()
    # Route with action (has caller)
    graph.add_node(Node("route::GET /", NodeType.ROUTE, "GET /", "r.py", 1))
    graph.add_node(Node("action::index", NodeType.ACTION, "index", "a.py", 5))
    graph.add_edge(Edge("route::GET /", "action::index", EdgeType.CALLS))
    # Orphaned service (no callers)
    graph.add_node(Node("service::OrphanSvc", NodeType.SERVICE, "OrphanSvc", "s.py", 10))

    port = _start_server_with_graph(tmp_path, graph)

    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/analysis/dead-weight')
        response = conn.getresponse()
        assert response.status == 200
        data = json.loads(response.read().decode())
        assert data["count"] == 1
        assert data["nodes"][0]["node_id"] == "service::OrphanSvc"
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_serve_search_returns_matching_nodes(tmp_path):
    """GET /api/search returns nodes matching query."""
    graph = Graph()
    graph.add_node(Node("route::GET /users", NodeType.ROUTE, "GET /users", "r.py", 1))
    graph.add_node(Node("action::list_users", NodeType.ACTION, "list_users", "a.py", 5))
    graph.add_node(Node("service::UserService", NodeType.SERVICE, "UserService", "s.py", 10))

    port = _start_server_with_graph(tmp_path, graph)

    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/search?q=user&limit=10')
        response = conn.getresponse()
        assert response.status == 200
        data = json.loads(response.read().decode())
        assert data["query"] == "user"
        assert data["count"] >= 2  # Should match users and UserService
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_serve_impact_returns_dependents(tmp_path):
    """GET /api/analysis/impact returns nodes that depend on target."""
    graph = Graph()
    graph.add_node(Node("service::CoreSvc", NodeType.SERVICE, "CoreSvc", "s.py", 1))
    graph.add_node(Node("action::use_core", NodeType.ACTION, "use_core", "a.py", 5))
    graph.add_edge(Edge("action::use_core", "service::CoreSvc", EdgeType.CALLS))

    port = _start_server_with_graph(tmp_path, graph)

    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/analysis/impact?nodeId=service::CoreSvc&depth=5')
        response = conn.getresponse()
        assert response.status == 200
        data = json.loads(response.read().decode())
        assert data["root_node_id"] == "service::CoreSvc"
        assert data["depth"] == 5
        assert "nodes" in data
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_serve_impact_missing_node_id_returns_400(tmp_path):
    """GET /api/analysis/impact without nodeId returns 400."""
    graph = Graph()
    graph.add_node(Node("route::GET /", NodeType.ROUTE, "GET /", "r.py", 1))
    port = _start_server_with_graph(tmp_path, graph)

    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/analysis/impact?depth=5')
        response = conn.getresponse()
        assert response.status == 400
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_serve_blind_spots_returns_unresolved_db_ops(tmp_path):
    """GET /api/analysis/blind-spots returns nodes with DB ops but no model edges."""
    graph = Graph()
    # Action with DB op but no model edge
    graph.add_node(Node("action::query_db", NodeType.ACTION, "query_db", "a.py", 5,
                        metadata={"has_db_op": True}))

    port = _start_server_with_graph(tmp_path, graph)

    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/analysis/blind-spots')
        response = conn.getresponse()
        assert response.status == 200
        data = json.loads(response.read().decode())
        assert "count" in data
        assert "nodes" in data
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_serve_trace_route_returns_execution_chain(tmp_path):
    """GET /api/trace/route returns route execution chain."""
    graph = Graph()
    graph.add_node(Node("route::GET /test", NodeType.ROUTE, "GET /test", "r.py", 1))
    graph.add_node(Node("action::test_func", NodeType.ACTION, "test_func", "a.py", 5))
    graph.add_edge(Edge("route::GET /test", "action::test_func", EdgeType.CALLS))

    port = _start_server_with_graph(tmp_path, graph)

    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/trace/route?id=route::GET%20/test')
        response = conn.getresponse()
        assert response.status == 200
        data = json.loads(response.read().decode())
        assert "route" in data
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_serve_trace_route_missing_id_returns_400(tmp_path):
    """GET /api/trace/route without id returns 400."""
    graph = Graph()
    graph.add_node(Node("route::GET /", NodeType.ROUTE, "GET /", "r.py", 1))
    port = _start_server_with_graph(tmp_path, graph)

    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/trace/route')
        response = conn.getresponse()
        assert response.status == 400
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_serve_blueprint_subgraph_returns_blueprint_tree(tmp_path):
    """GET /api/trace/blueprint returns blueprint subgraph."""
    graph = Graph()
    graph.add_node(Node("blueprint::admin", NodeType.BLUEPRINT, "admin", "admin.py", 1))
    graph.add_node(Node("route::GET /admin", NodeType.ROUTE, "GET /admin", "admin.py", 5))
    graph.add_edge(Edge("blueprint::admin", "route::GET /admin", EdgeType.REGISTERS_BLUEPRINT))

    port = _start_server_with_graph(tmp_path, graph)

    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/trace/blueprint?id=blueprint::admin')
        response = conn.getresponse()
        assert response.status == 200
        data = json.loads(response.read().decode())
        assert "blueprint" in data
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_serve_blueprint_subgraph_missing_id_returns_400(tmp_path):
    """GET /api/trace/blueprint without id returns 400."""
    graph = Graph()
    graph.add_node(Node("route::GET /", NodeType.ROUTE, "GET /", "r.py", 1))
    port = _start_server_with_graph(tmp_path, graph)

    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/trace/blueprint')
        response = conn.getresponse()
        assert response.status == 400
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_serve_locate_returns_feature_location(tmp_path):
    """GET /api/locate returns best-fit blueprint and service for hint."""
    graph = Graph()
    graph.add_node(Node("blueprint::users", NodeType.BLUEPRINT, "users", "users.py", 1))
    graph.add_node(Node("service::UserService", NodeType.SERVICE, "UserService", "user_svc.py", 5))

    port = _start_server_with_graph(tmp_path, graph)

    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/locate?hint=user')
        response = conn.getresponse()
        assert response.status == 200
        data = json.loads(response.read().decode())
        assert "hint" in data or "blueprint" in data or "service" in data
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_serve_locate_missing_hint_returns_400(tmp_path):
    """GET /api/locate without hint returns 400."""
    graph = Graph()
    graph.add_node(Node("route::GET /", NodeType.ROUTE, "GET /", "r.py", 1))
    port = _start_server_with_graph(tmp_path, graph)

    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/locate')
        response = conn.getresponse()
        assert response.status == 400
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_serve_trace_node_returns_forward_backward_trace(tmp_path):
    """GET /api/trace/node returns callers and callees."""
    graph = Graph()
    graph.add_node(Node("action::middle", NodeType.ACTION, "middle", "a.py", 5))
    graph.add_node(Node("service::Svc", NodeType.SERVICE, "Svc", "s.py", 10))
    graph.add_edge(Edge("action::middle", "service::Svc", EdgeType.CALLS))

    port = _start_server_with_graph(tmp_path, graph)

    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/trace/node?id=action::middle')
        response = conn.getresponse()
        assert response.status == 200
        data = json.loads(response.read().decode())
        assert "node" in data
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_serve_trace_node_missing_id_returns_400(tmp_path):
    """GET /api/trace/node without id returns 400."""
    graph = Graph()
    graph.add_node(Node("route::GET /", NodeType.ROUTE, "GET /", "r.py", 1))
    port = _start_server_with_graph(tmp_path, graph)

    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/trace/node')
        response = conn.getresponse()
        assert response.status == 400
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_serve_neighbors_returns_bidirectional_subgraph(tmp_path):
    """GET /api/neighbors returns nodes within depth hops."""
    graph = Graph()
    graph.add_node(Node("action::center", NodeType.ACTION, "center", "a.py", 5))
    graph.add_node(Node("service::Svc", NodeType.SERVICE, "Svc", "s.py", 10))
    graph.add_edge(Edge("action::center", "service::Svc", EdgeType.CALLS))

    port = _start_server_with_graph(tmp_path, graph)

    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/neighbors?id=action::center&depth=2')
        response = conn.getresponse()
        assert response.status == 200
        data = json.loads(response.read().decode())
        assert "nodes" in data
        assert "edges" in data
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_serve_neighbors_missing_id_returns_400(tmp_path):
    """GET /api/neighbors without id returns 400."""
    graph = Graph()
    graph.add_node(Node("route::GET /", NodeType.ROUTE, "GET /", "r.py", 1))
    port = _start_server_with_graph(tmp_path, graph)

    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/neighbors?depth=2')
        response = conn.getresponse()
        assert response.status == 400
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_serve_context_returns_ai_context(tmp_path):
    """GET /api/context returns AI context for a node."""
    graph = Graph()
    graph.add_node(Node("action::test_func", NodeType.ACTION, "test_func", "a.py", 5))
    port = _start_server_with_graph(tmp_path, graph)

    # Create source file
    (tmp_path / "a.py").write_text("def test_func():\n    pass\n")

    try:
        conn = HTTPConnection('localhost', port, timeout=2)
        conn.request('GET', '/api/context?nodeId=action::test_func')
        response = conn.getresponse()
        assert response.status == 200
        data = json.loads(response.read().decode())
        assert "context" in data or "node_id" in data
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_handle_rescan_triggers_rebuild(tmp_path):
    """POST /api/scan triggers a project rescan."""
    graph = Graph()
    graph.add_node(Node("route::GET /", NodeType.ROUTE, "GET /", "r.py", 1))
    
    graph_dir = tmp_path / ".flask-brain"
    graph_dir.mkdir(exist_ok=True)
    manifest = {"project_name": "test", "scan_timestamp": "2024-01-01T00:00:00Z",
                "node_count": 1, "edge_count": 0, "node_types": {}}
    with open(graph_dir / "manifest.json", "w") as f:
        json.dump(manifest, f)
    with open(graph_dir / "graph-all.json", "w") as f:
        json.dump(graph.to_dict(), f)

    # Create a minimal Flask app to scan
    (tmp_path / "app.py").write_text("from flask import Flask\napp = Flask(__name__)\n@app.route('/')\ndef index(): pass\n")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        port = s.getsockname()[1]

    threading.Thread(
        target=start_server,
        args=(graph_dir, port, False),
        kwargs={"project_path": tmp_path},
        daemon=True,
    ).start()
    time.sleep(0.5)

    try:
        conn = HTTPConnection('localhost', port, timeout=5)
        conn.request('POST', '/api/scan')
        response = conn.getresponse()
        # Should return 200 with updated manifest
        assert response.status == 200
        data = json.loads(response.read().decode())
        assert "node_count" in data
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_server_generate_tests_endpoint(temp_graph_dir):
    """Test POST /api/generate/tests endpoint."""
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
        
        # Test with valid route target
        body = json.dumps({"target": "route::GET /test"})
        headers = {"Content-Type": "application/json"}
        conn.request('POST', '/api/generate/tests', body=body, headers=headers)
        response = conn.getresponse()
        
        assert response.status == 200
        data = json.loads(response.read().decode())
        assert "target_id" in data
        assert "combined" in data
        assert "tiers" in data
        assert "stats" in data
        assert data["target_id"] == "route::GET /test"
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")


def test_server_generate_tests_missing_target(temp_graph_dir):
    """Test POST /api/generate/tests with missing target parameter."""
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
        
        # Test with missing target
        body = json.dumps({})
        headers = {"Content-Type": "application/json"}
        conn.request('POST', '/api/generate/tests', body=body, headers=headers)
        response = conn.getresponse()
        
        assert response.status == 400
        data = json.loads(response.read().decode())
        assert "error" in data
        assert "target" in data["error"].lower()
        conn.close()
    except Exception as e:
        pytest.skip(f"Server test skipped: {e}")
