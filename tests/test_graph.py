"""Tests for graph data model."""

import pytest
from pathlib import Path
import json
import tempfile
from flask_brain.graph import (
    Node, Edge, Graph, GraphBuilder,
    NodeType, EdgeType
)


def test_node_creation():
    """Test creating a node."""
    node = Node(
        id="route::GET /users",
        type=NodeType.ROUTE,
        label="GET /users",
        file_path="/app/routes.py",
        line_number=10,
        metadata={"methods": ["GET"]}
    )
    assert node.id == "route::GET /users"
    assert node.type == NodeType.ROUTE
    assert node.label == "GET /users"
    assert node.metadata["methods"] == ["GET"]


def test_node_to_dict():
    """Test converting node to dictionary."""
    node = Node(
        id="model::User",
        type=NodeType.MODEL,
        label="User",
        file_path="/app/models.py",
        line_number=5,
        metadata={"columns": ["id", "name"]}
    )
    data = node.to_dict()
    assert data["id"] == "model::User"
    assert data["type"] == "model"
    assert data["metadata"]["columns"] == ["id", "name"]


def test_node_from_dict():
    """Test creating node from dictionary."""
    data = {
        "id": "service::UserService",
        "type": "service",
        "label": "UserService",
        "file_path": "/app/services.py",
        "line_number": 20,
        "metadata": {"methods": ["get_user", "create_user"]}
    }
    node = Node.from_dict(data)
    assert node.id == "service::UserService"
    assert node.type == NodeType.SERVICE
    assert node.metadata["methods"] == ["get_user", "create_user"]


def test_edge_creation():
    """Test creating an edge."""
    edge = Edge(
        source="route::GET /users",
        target="action::list_users",
        type=EdgeType.CALLS
    )
    assert edge.source == "route::GET /users"
    assert edge.target == "action::list_users"
    assert edge.type == EdgeType.CALLS


def test_edge_to_dict():
    """Test converting edge to dictionary."""
    edge = Edge(
        source="action::list_users",
        target="model::User",
        type=EdgeType.USES_MODEL,
        metadata={"operation": "query"}
    )
    data = edge.to_dict()
    assert data["source"] == "action::list_users"
    assert data["target"] == "model::User"
    assert data["type"] == "uses_model"
    assert data["metadata"]["operation"] == "query"


def test_edge_from_dict():
    """Test creating edge from dictionary."""
    data = {
        "source": "model::User",
        "target": "model::Order",
        "type": "has_relationship",
        "metadata": {"relationship_type": "one_to_many"}
    }
    edge = Edge.from_dict(data)
    assert edge.source == "model::User"
    assert edge.target == "model::Order"
    assert edge.type == EdgeType.HAS_RELATIONSHIP


def test_graph_add_node():
    """Test adding nodes to graph."""
    graph = Graph()
    node1 = Node("route::GET /users", NodeType.ROUTE, "GET /users", "/app/routes.py", 10)
    node2 = Node("model::User", NodeType.MODEL, "User", "/app/models.py", 5)
    
    graph.add_node(node1)
    graph.add_node(node2)
    
    assert len(graph.nodes) == 2
    assert "route::GET /users" in graph.nodes
    assert "model::User" in graph.nodes


def test_graph_add_node_merge_metadata():
    """Test that adding node with same ID merges metadata."""
    graph = Graph()
    node1 = Node("model::User", NodeType.MODEL, "User", "/app/models.py", 5, 
                 metadata={"columns": ["id", "name"]})
    node2 = Node("model::User", NodeType.MODEL, "User", "/app/models.py", 5,
                 metadata={"complexity": 5})
    
    graph.add_node(node1)
    graph.add_node(node2)
    
    assert len(graph.nodes) == 1
    node = graph.get_node("model::User")
    assert "columns" in node.metadata
    assert "complexity" in node.metadata


def test_graph_add_edge():
    """Test adding edges to graph."""
    graph = Graph()
    graph.add_node(Node("route::GET /users", NodeType.ROUTE, "GET /users", "/app/routes.py", 1))
    graph.add_node(Node("action::list_users", NodeType.ACTION, "list_users", "/app/routes.py", 5))
    graph.add_node(Node("model::User", NodeType.MODEL, "User", "/app/models.py", 1))
    edge1 = Edge("route::GET /users", "action::list_users", EdgeType.CALLS)
    edge2 = Edge("action::list_users", "model::User", EdgeType.USES_MODEL)
    
    graph.add_edge(edge1)
    graph.add_edge(edge2)
    
    assert len(graph.edges) == 2


def test_graph_add_edge_no_duplicates():
    """Test that duplicate edges are not added."""
    graph = Graph()
    graph.add_node(Node("route::GET /users", NodeType.ROUTE, "GET /users", "/app/routes.py", 1))
    graph.add_node(Node("action::list_users", NodeType.ACTION, "list_users", "/app/routes.py", 5))
    edge1 = Edge("route::GET /users", "action::list_users", EdgeType.CALLS)
    edge2 = Edge("route::GET /users", "action::list_users", EdgeType.CALLS)
    
    graph.add_edge(edge1)
    graph.add_edge(edge2)
    
    assert len(graph.edges) == 1


def test_graph_get_edges_from():
    """Test getting edges from a node."""
    graph = Graph()
    graph.add_node(Node("route::GET /users", NodeType.ROUTE, "GET /users", "/app/routes.py", 1))
    graph.add_node(Node("action::list_users", NodeType.ACTION, "list_users", "/app/routes.py", 5))
    graph.add_node(Node("action::show_user", NodeType.ACTION, "show_user", "/app/routes.py", 10))
    graph.add_node(Node("model::User", NodeType.MODEL, "User", "/app/models.py", 1))
    edge1 = Edge("route::GET /users", "action::list_users", EdgeType.CALLS)
    edge2 = Edge("route::GET /users", "action::show_user", EdgeType.CALLS)
    edge3 = Edge("action::list_users", "model::User", EdgeType.USES_MODEL)
    
    graph.add_edge(edge1)
    graph.add_edge(edge2)
    graph.add_edge(edge3)
    
    edges = graph.get_edges_from("route::GET /users")
    assert len(edges) == 2


def test_graph_get_edges_to():
    """Test getting edges to a node."""
    graph = Graph()
    graph.add_node(Node("route::GET /users", NodeType.ROUTE, "GET /users", "/app/routes.py", 1))
    graph.add_node(Node("route::POST /users", NodeType.ROUTE, "POST /users", "/app/routes.py", 20))
    graph.add_node(Node("action::list_users", NodeType.ACTION, "list_users", "/app/routes.py", 5))
    graph.add_node(Node("model::User", NodeType.MODEL, "User", "/app/models.py", 1))
    edge1 = Edge("route::GET /users", "action::list_users", EdgeType.CALLS)
    edge2 = Edge("route::POST /users", "action::list_users", EdgeType.CALLS)
    edge3 = Edge("action::list_users", "model::User", EdgeType.USES_MODEL)
    
    graph.add_edge(edge1)
    graph.add_edge(edge2)
    graph.add_edge(edge3)
    
    edges = graph.get_edges_to("action::list_users")
    assert len(edges) == 2


def test_graph_to_dict():
    """Test converting graph to dictionary."""
    graph = Graph()
    node = Node("route::GET /users", NodeType.ROUTE, "GET /users", "/app/routes.py", 10)
    graph.add_node(node)
    # edge target doesn't exist — add it so add_edge doesn't drop it
    graph.add_node(Node("action::list_users", NodeType.ACTION, "list_users", "/app/routes.py", 15))
    edge = Edge("route::GET /users", "action::list_users", EdgeType.CALLS)
    
    graph.add_node(node)
    graph.add_edge(edge)
    
    data = graph.to_dict()
    assert len(data["nodes"]) == 2
    assert len(data["edges"]) == 1
    assert data["nodes"][0]["id"] == "route::GET /users"


def test_graph_from_dict():
    """Test creating graph from dictionary."""
    data = {
        "nodes": [
            {
                "id": "route::GET /users",
                "type": "route",
                "label": "GET /users",
                "file_path": "/app/routes.py",
                "line_number": 10,
                "metadata": {}
            },
            {
                "id": "action::list_users",
                "type": "action",
                "label": "list_users",
                "file_path": "/app/routes.py",
                "line_number": 15,
                "metadata": {}
            }
        ],
        "edges": [
            {
                "source": "route::GET /users",
                "target": "action::list_users",
                "type": "calls",
                "metadata": {}
            }
        ]
    }
    
    graph = Graph.from_dict(data)
    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1


def test_graph_write():
    """Test writing graph to JSON files."""
    graph = Graph()
    
    # Add some nodes
    route_node = Node("route::GET /users", NodeType.ROUTE, "GET /users", "/app/routes.py", 10)
    action_node = Node("action::list_users", NodeType.ACTION, "list_users", "/app/routes.py", 11)
    model_node = Node("model::User", NodeType.MODEL, "User", "/app/models.py", 5)
    
    graph.add_node(route_node)
    graph.add_node(action_node)
    graph.add_node(model_node)
    
    # Add edges
    edge1 = Edge("route::GET /users", "action::list_users", EdgeType.CALLS)
    edge2 = Edge("action::list_users", "model::User", EdgeType.USES_MODEL)
    
    graph.add_edge(edge1)
    graph.add_edge(edge2)
    
    # Write to temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        graph.write(output_dir)
        
        # Check manifest exists
        manifest_path = output_dir / "manifest.json"
        assert manifest_path.exists()
        
        with open(manifest_path) as f:
            manifest = json.load(f)
            assert manifest["node_count"] == 3
            assert manifest["edge_count"] == 2
        
        # Check graph-all.json exists
        assert (output_dir / "graph-all.json").exists()
        
        # Check graph-routes.json exists
        assert (output_dir / "graph-routes.json").exists()
        
        # Check per-route graph exists
        route_files = list(output_dir.glob("graph-route_*.json"))
        assert len(route_files) == 1


def test_graph_builder_add_scanner_output():
    """Test adding scanner output to graph builder."""
    builder = GraphBuilder()
    
    nodes = [
        Node("route::GET /users", NodeType.ROUTE, "GET /users", "/app/routes.py", 10),
        Node("model::User", NodeType.MODEL, "User", "/app/models.py", 5)
    ]
    edges = [
        Edge("route::GET /users", "model::User", EdgeType.USES_MODEL)
    ]
    
    builder.add_scanner_output(nodes, edges)
    graph = builder.get_graph()
    
    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1


def test_graph_builder_merge_multiple_scanners():
    """Test that graph builder merges output from multiple scanners."""
    builder = GraphBuilder()
    
    # First scanner output
    nodes1 = [Node("route::GET /users", NodeType.ROUTE, "GET /users", "/app/routes.py", 10)]
    edges1 = []
    
    # Second scanner output (adds metadata to same node)
    nodes2 = [Node("route::GET /users", NodeType.ROUTE, "GET /users", "/app/routes.py", 10,
                   metadata={"complexity": 5})]
    edges2 = []
    
    builder.add_scanner_output(nodes1, edges1)
    builder.add_scanner_output(nodes2, edges2)
    
    graph = builder.get_graph()
    assert len(graph.nodes) == 1
    node = graph.get_node("route::GET /users")
    assert "complexity" in node.metadata


def test_graph_write_includes_scan_timestamp():
    """Test that manifest includes a valid scan_timestamp."""
    from datetime import datetime
    
    graph = Graph()
    route_node = Node("route::GET /users", NodeType.ROUTE, "GET /users", "/app/routes.py", 10)
    graph.add_node(route_node)
    
    # Write to temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        graph.write(output_dir)
        
        # Check manifest has scan_timestamp
        manifest_path = output_dir / "manifest.json"
        assert manifest_path.exists()
        
        with open(manifest_path) as f:
            manifest = json.load(f)
            assert manifest["scan_timestamp"] is not None
            assert manifest["scan_timestamp"] != ""
            
            # Verify it's a valid ISO datetime
            timestamp = datetime.fromisoformat(manifest["scan_timestamp"].replace('Z', '+00:00'))
            assert timestamp is not None


# ── dead_weight() tests ───────────────────────────────────────────────────────

def _make_graph_with_dead_nodes() -> Graph:
    """Helper: build a small graph with one called and one uncalled service."""
    g = Graph()
    route = Node("route::GET /home", NodeType.ROUTE, "GET /home", "routes.py", 1)
    called_svc = Node("service::active_svc", NodeType.SERVICE, "active_svc", "services.py", 10)
    dead_svc = Node("service::dead_svc", NodeType.SERVICE, "dead_svc", "services.py", 30)
    dead_action = Node("action::orphan_action", NodeType.ACTION, "orphan_action", "views.py", 5)
    model = Node("model::User", NodeType.MODEL, "User", "models.py", 1)

    g.add_node(route)
    g.add_node(called_svc)
    g.add_node(dead_svc)
    g.add_node(dead_action)
    g.add_node(model)

    # route → called_svc (so called_svc has an incoming edge)
    g.add_edge(Edge(route.id, called_svc.id, EdgeType.CALLS))
    return g


def test_dead_weight_returns_uncalled_nodes():
    """dead_weight() should return SERVICE/ACTION/TASK nodes with no incoming edges."""
    g = _make_graph_with_dead_nodes()
    dead = g.dead_weight()
    dead_ids = {n.id for n in dead}

    assert "service::dead_svc" in dead_ids
    assert "action::orphan_action" in dead_ids


def test_dead_weight_excludes_called_nodes():
    """dead_weight() must NOT include nodes that are targets of at least one edge."""
    g = _make_graph_with_dead_nodes()
    dead = g.dead_weight()
    dead_ids = {n.id for n in dead}

    assert "service::active_svc" not in dead_ids


def test_dead_weight_excludes_routes_and_models():
    """ROUTE and MODEL nodes must never appear in dead_weight results."""
    g = _make_graph_with_dead_nodes()
    dead = g.dead_weight()
    for node in dead:
        assert node.type not in (NodeType.ROUTE, NodeType.MODEL)


def test_dead_weight_custom_node_types():
    """dead_weight() with custom node_types should only check those types."""
    g = _make_graph_with_dead_nodes()
    # Only ask about SERVICE nodes
    dead = g.dead_weight(node_types={NodeType.SERVICE})
    dead_ids = {n.id for n in dead}

    assert "service::dead_svc" in dead_ids
    assert "action::orphan_action" not in dead_ids  # ACTION excluded from check


def test_dead_weight_empty_graph():
    """dead_weight() on an empty graph should return empty list."""
    g = Graph()
    assert g.dead_weight() == []


def test_dead_weight_sorted():
    """dead_weight() result must be sorted by (type, label)."""
    g = Graph()
    # Add several uncalled services/actions in non-alphabetical order
    for label in ["z_svc", "a_svc", "m_svc"]:
        g.add_node(Node(f"service::{label}", NodeType.SERVICE, label, "s.py", 1))

    dead = g.dead_weight()
    labels = [n.label for n in dead]
    assert labels == sorted(labels)


# ── blind_spots() tests ───────────────────────────────────────────────────────

def _make_graph_with_blind_spots() -> Graph:
    """Helper: build a graph mixing nodes with/without db_ops and model edges."""
    g = Graph()

    # Node WITH db ops AND a uses_model edge → NOT a blind spot
    n_linked = Node("action::linked", NodeType.ACTION, "linked", "v.py", 1,
                    metadata={"db_op_count": 3})
    model = Node("model::User", NodeType.MODEL, "User", "m.py", 1)
    g.add_node(n_linked)
    g.add_node(model)
    g.add_edge(Edge(n_linked.id, model.id, EdgeType.USES_MODEL))

    # Node WITH db ops but NO uses_model edge → IS a blind spot
    n_blind = Node("action::blind", NodeType.ACTION, "blind", "v.py", 10,
                   metadata={"db_op_count": 5})
    g.add_node(n_blind)

    # Service WITH db ops but NO uses_model edge → IS a blind spot
    n_svc = Node("service::svc_blind", NodeType.SERVICE, "svc_blind", "s.py", 1,
                 metadata={"db_op_count": 2})
    g.add_node(n_svc)

    # Node with db_op_count = 0 → NOT a blind spot
    n_clean = Node("action::clean", NodeType.ACTION, "clean", "v.py", 20,
                   metadata={"db_op_count": 0})
    g.add_node(n_clean)

    # Node with no db_op_count key at all → NOT a blind spot
    n_none = Node("action::no_ops", NodeType.ACTION, "no_ops", "v.py", 30)
    g.add_node(n_none)

    return g


def test_blind_spots_detects_unresolved_db_callers():
    """blind_spots() should return nodes with db ops but no USES_MODEL edge."""
    g = _make_graph_with_blind_spots()
    blind = g.blind_spots()
    blind_ids = {n.id for n in blind}

    assert "action::blind" in blind_ids
    assert "service::svc_blind" in blind_ids


def test_blind_spots_excludes_linked_nodes():
    """blind_spots() must NOT include nodes that have a USES_MODEL edge."""
    g = _make_graph_with_blind_spots()
    blind = g.blind_spots()
    blind_ids = {n.id for n in blind}

    assert "action::linked" not in blind_ids


def test_blind_spots_excludes_zero_db_ops():
    """blind_spots() must not flag nodes with no DB operations."""
    g = _make_graph_with_blind_spots()
    blind = g.blind_spots()
    blind_ids = {n.id for n in blind}

    assert "action::clean" not in blind_ids
    assert "action::no_ops" not in blind_ids


def test_blind_spots_sorted_by_db_op_count_desc():
    """blind_spots() result must be sorted descending by db_op_count."""
    g = _make_graph_with_blind_spots()
    blind = g.blind_spots()
    counts = [n.metadata.get("db_op_count", 0) for n in blind]
    assert counts == sorted(counts, reverse=True)


def test_blind_spots_empty_graph():
    """blind_spots() on an empty graph returns empty list."""
    assert Graph().blind_spots() == []


def test_blind_spots_custom_node_types():
    """blind_spots() with custom node_types only checks those types."""
    g = _make_graph_with_blind_spots()
    # Only check ACTION nodes
    blind = g.blind_spots(node_types={NodeType.ACTION})
    blind_ids = {n.id for n in blind}

    assert "action::blind" in blind_ids
    assert "service::svc_blind" not in blind_ids  # SERVICE excluded


# ── impact_subgraph() tests ───────────────────────────────────────────────────

def _make_impact_graph() -> Graph:
    """
    Build a chain: routeA → svcX → svcY (target)
                   routeB → svcY (direct)
                   routeC → svcZ  (unrelated)
    """
    g = Graph()

    nodes = {
        "route_a": Node("route::GET /a", NodeType.ROUTE, "GET /a", "r.py", 1),
        "route_b": Node("route::GET /b", NodeType.ROUTE, "GET /b", "r.py", 2),
        "route_c": Node("route::GET /c", NodeType.ROUTE, "GET /c", "r.py", 3),
        "svc_x":   Node("service::svc_x", NodeType.SERVICE, "svc_x", "s.py", 1),
        "svc_y":   Node("service::svc_y", NodeType.SERVICE, "svc_y", "s.py", 10),
        "svc_z":   Node("service::svc_z", NodeType.SERVICE, "svc_z", "s.py", 20),
    }
    for n in nodes.values():
        g.add_node(n)

    g.add_edge(Edge("route::GET /a", "service::svc_x", EdgeType.CALLS))
    g.add_edge(Edge("service::svc_x", "service::svc_y", EdgeType.CALLS))
    g.add_edge(Edge("route::GET /b", "service::svc_y", EdgeType.CALLS))
    g.add_edge(Edge("route::GET /c", "service::svc_z", EdgeType.CALLS))
    return g


def test_impact_subgraph_includes_all_ancestors():
    """impact_subgraph() must include all nodes that transitively call the target."""
    g = _make_impact_graph()
    sub = g.impact_subgraph("service::svc_y")
    sub_ids = set(sub.nodes.keys())

    # svc_y itself
    assert "service::svc_y" in sub_ids
    # direct caller
    assert "route::GET /b" in sub_ids
    # transitive callers (routeA → svcX → svcY)
    assert "service::svc_x" in sub_ids
    assert "route::GET /a" in sub_ids


def test_impact_subgraph_excludes_unrelated_nodes():
    """impact_subgraph() must NOT include nodes not in the ancestor chain."""
    g = _make_impact_graph()
    sub = g.impact_subgraph("service::svc_y")
    sub_ids = set(sub.nodes.keys())

    assert "route::GET /c" not in sub_ids
    assert "service::svc_z" not in sub_ids


def test_impact_subgraph_includes_self():
    """impact_subgraph() must include the start node itself."""
    g = _make_impact_graph()
    sub = g.impact_subgraph("service::svc_y")
    assert "service::svc_y" in sub.nodes


def test_impact_subgraph_depth_limit():
    """impact_subgraph() must respect the depth parameter."""
    g = _make_impact_graph()
    # depth=1 means only direct callers
    sub = g.impact_subgraph("service::svc_y", depth=1)
    sub_ids = set(sub.nodes.keys())

    assert "service::svc_y" in sub_ids
    assert "route::GET /b" in sub_ids     # direct caller — included
    assert "service::svc_x" in sub_ids   # also direct caller of svc_y? No — svc_x calls svc_y
    # routeA is depth=2 away (routeA→svcX→svcY) — must be excluded
    assert "route::GET /a" not in sub_ids


def test_impact_subgraph_invalid_node():
    """impact_subgraph() raises ValueError for unknown node IDs."""
    g = _make_impact_graph()
    with pytest.raises(ValueError, match="not found"):
        g.impact_subgraph("service::does_not_exist")


def test_impact_subgraph_no_callers():
    """impact_subgraph() on a node with no callers returns only that node."""
    g = _make_impact_graph()
    # svc_z is called by routeC; svc_z itself has no callers
    sub = g.impact_subgraph("route::GET /c")
    sub_ids = set(sub.nodes.keys())

    assert "route::GET /c" in sub_ids
    # No one calls routeC, so it's just the node itself
    assert len(sub_ids) == 1


# ── search() tests ────────────────────────────────────────────────────────────

def _make_search_graph() -> Graph:
    """Build a graph with varied nodes for search testing."""
    g = Graph()

    route = Node("route::GET /users", NodeType.ROUTE, "GET /users", "routes/users.py", 1,
                 metadata={"methods": ["GET"], "blueprint": "users"})
    action = Node("action::list_users", NodeType.ACTION, "list_users", "views/users.py", 10,
                  metadata={"complexity": 5, "blueprint": "users"})
    svc = Node("service::user_service", NodeType.SERVICE, "user_service", "services/user.py", 1,
               metadata={"complexity": 25})
    model_user = Node("model::User", NodeType.MODEL, "User", "models/user.py", 1,
                      metadata={"columns": {"id": {"type": "Integer"}}})
    model_order = Node("model::Order", NodeType.MODEL, "Order", "models/order.py", 1)
    task = Node("task::send_email", NodeType.TASK, "send_email", "tasks.py", 1)

    for n in [route, action, svc, model_user, model_order, task]:
        g.add_node(n)

    # action uses User model
    g.add_edge(Edge(action.id, model_user.id, EdgeType.USES_MODEL))
    return g


def test_search_free_text_label():
    """Free text search matches on node label."""
    g = _make_search_graph()
    results = g.search("user_service")
    assert any(n.id == "service::user_service" for n in results)


def test_search_free_text_multiple_terms():
    """All free-text terms must match (AND logic)."""
    g = _make_search_graph()
    # "user" appears in many; "service" narrows to service file
    results = g.search("user service")
    ids = {n.id for n in results}
    assert "service::user_service" in ids
    # route label "GET /users" does NOT contain "service"
    assert "route::GET /users" not in ids


def test_search_type_predicate():
    """type= predicate filters to a specific node type."""
    g = _make_search_graph()
    results = g.search("type=route")
    assert all(n.type == NodeType.ROUTE for n in results)
    assert any(n.id == "route::GET /users" for n in results)


def test_search_model_predicate():
    """model= predicate finds nodes with a USES_MODEL edge to that model."""
    g = _make_search_graph()
    results = g.search("model=User")
    ids = {n.id for n in results}
    assert "action::list_users" in ids
    # user_service has no uses_model edge
    assert "service::user_service" not in ids


def test_search_complexity_gt():
    """complexity> predicate filters nodes by complexity."""
    g = _make_search_graph()
    results = g.search("complexity>10")
    ids = {n.id for n in results}
    assert "service::user_service" in ids  # cx=25 > 10
    assert "action::list_users" not in ids  # cx=5 not > 10


def test_search_complexity_lt():
    """complexity< predicate works correctly."""
    g = _make_search_graph()
    results = g.search("complexity<10")
    assert all((n.metadata.get("complexity") or 0) < 10 for n in results)


def test_search_combined_predicate_and_text():
    """Combining predicates and text terms applies AND logic."""
    g = _make_search_graph()
    results = g.search("type=action users")
    ids = {n.id for n in results}
    # list_users is an action and contains "users" in file_path
    assert "action::list_users" in ids
    # user_service is a service — should be excluded
    assert "service::user_service" not in ids


def test_search_empty_query():
    """Empty query returns empty list."""
    g = _make_search_graph()
    assert g.search("") == []


def test_search_no_match():
    """Query that matches nothing returns empty list."""
    g = _make_search_graph()
    assert g.search("xyzzy_does_not_exist_12345") == []


def test_search_limit():
    """search() respects the limit parameter."""
    g = Graph()
    for i in range(20):
        g.add_node(Node(f"service::svc_{i}", NodeType.SERVICE, f"svc_{i}", "s.py", i))
    results = g.search("svc", limit=5)
    assert len(results) == 5


def test_search_sorted_by_label():
    """search() results are sorted alphabetically by label."""
    g = _make_search_graph()
    results = g.search("type=model")
    labels = [n.label for n in results]
    assert labels == sorted(labels)


# ── top_risk() tests ──────────────────────────────────────────────────────────

def _make_risk_graph() -> Graph:
    """Graph with nodes that have risk_score metadata."""
    g = Graph()
    nodes = [
        Node("action::high_risk", NodeType.ACTION, "high_risk", "a.py", 1,
             metadata={"risk_score": 80, "churn_count": 8, "complexity": 10}),
        Node("action::med_risk", NodeType.ACTION, "med_risk", "b.py", 2,
             metadata={"risk_score": 30, "churn_count": 3, "complexity": 10}),
        Node("service::low_risk", NodeType.SERVICE, "low_risk", "c.py", 3,
             metadata={"risk_score": 5, "churn_count": 1, "complexity": 5}),
        Node("route::no_risk", NodeType.ROUTE, "no_risk", "d.py", 4,
             metadata={}),
        Node("action::zero_risk", NodeType.ACTION, "zero_risk", "e.py", 5,
             metadata={"risk_score": 0}),
    ]
    for n in nodes:
        g.add_node(n)
    return g


def test_top_risk_sorted_descending():
    """top_risk() returns nodes sorted by risk_score descending."""
    g = _make_risk_graph()
    results = g.top_risk()
    scores = [n.metadata.get("risk_score", 0) for n in results]
    assert scores == sorted(scores, reverse=True)


def test_top_risk_excludes_zero_and_missing():
    """top_risk() excludes nodes with risk_score == 0 or missing risk_score."""
    g = _make_risk_graph()
    results = g.top_risk()
    ids = {n.id for n in results}
    assert "action::zero_risk" not in ids
    assert "route::no_risk" not in ids


def test_top_risk_limit():
    """top_risk() respects the limit parameter."""
    g = Graph()
    for i in range(20):
        g.add_node(Node(f"action::a{i}", NodeType.ACTION, f"a{i}", "x.py", i,
                        metadata={"risk_score": i + 1}))
    results = g.top_risk(limit=5)
    assert len(results) == 5
    # Should be top 5 highest scores
    scores = [n.metadata["risk_score"] for n in results]
    assert scores == sorted(scores, reverse=True)


def test_top_risk_default_limit_50():
    """top_risk() default limit is 50."""
    g = Graph()
    for i in range(60):
        g.add_node(Node(f"action::a{i}", NodeType.ACTION, f"a{i}", "x.py", i,
                        metadata={"risk_score": i + 1}))
    results = g.top_risk()
    assert len(results) == 50


def test_top_risk_empty_graph():
    """top_risk() on empty graph returns empty list."""
    assert Graph().top_risk() == []
