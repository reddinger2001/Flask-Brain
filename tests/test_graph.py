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
    edge1 = Edge("route::GET /users", "action::list_users", EdgeType.CALLS)
    edge2 = Edge("action::list_users", "model::User", EdgeType.USES_MODEL)
    
    graph.add_edge(edge1)
    graph.add_edge(edge2)
    
    assert len(graph.edges) == 2


def test_graph_add_edge_no_duplicates():
    """Test that duplicate edges are not added."""
    graph = Graph()
    edge1 = Edge("route::GET /users", "action::list_users", EdgeType.CALLS)
    edge2 = Edge("route::GET /users", "action::list_users", EdgeType.CALLS)
    
    graph.add_edge(edge1)
    graph.add_edge(edge2)
    
    assert len(graph.edges) == 1


def test_graph_get_edges_from():
    """Test getting edges from a node."""
    graph = Graph()
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
    edge = Edge("route::GET /users", "action::list_users", EdgeType.CALLS)
    
    graph.add_node(node)
    graph.add_edge(edge)
    
    data = graph.to_dict()
    assert len(data["nodes"]) == 1
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
    assert len(graph.nodes) == 1
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
