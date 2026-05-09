"""Tests for QueryTracer."""

import pytest
from pathlib import Path

from flask_brain.scanners.query_tracer import QueryTracer
from flask_brain.graph import Graph, Node, NodeType


@pytest.fixture
def flat_app_path():
    """Path to flat app fixture."""
    return Path(__file__).parent / "fixtures" / "flat_app"


@pytest.fixture
def factory_app_path():
    """Path to factory app fixture."""
    return Path(__file__).parent / "fixtures" / "factory_app"


def test_query_tracer_returns_no_nodes_or_edges(flat_app_path):
    """Test that tracer returns empty lists (it enriches, doesn't create)."""
    tracer = QueryTracer(flat_app_path)
    nodes, edges = tracer.scan()
    
    assert nodes == []
    assert edges == []


def test_query_tracer_enriches_nodes_with_db_operations(flat_app_path):
    """Test that tracer enriches nodes with db_operations metadata."""
    tracer = QueryTracer(flat_app_path)
    
    graph = Graph()
    graph.add_node(Node(
        id="service::get_user_by_id",
        type=NodeType.SERVICE,
        label="get_user_by_id",
        file_path="app.py",
        line_number=41,
        metadata={}
    ))
    
    tracer.enrich(graph)
    
    node = graph.nodes["service::get_user_by_id"]
    assert "db_operations" in node.metadata
    assert isinstance(node.metadata["db_operations"], list)


def test_query_tracer_detects_read_operations(flat_app_path):
    """Test detection of READ operations (query, filter, all, get, first)."""
    tracer = QueryTracer(flat_app_path)
    
    graph = Graph()
    graph.add_node(Node(
        id="service::get_user_by_id",
        type=NodeType.SERVICE,
        label="get_user_by_id",
        file_path="app.py",
        line_number=41,
        metadata={}
    ))
    
    tracer.enrich(graph)
    
    node = graph.nodes["service::get_user_by_id"]
    operations = node.metadata.get("db_operations", [])
    
    # get_user_by_id calls User.query.get()
    read_ops = [op for op in operations if op["type"] == "READ"]
    assert len(read_ops) > 0


def test_query_tracer_detects_write_operations(flat_app_path):
    """Test detection of WRITE operations (add, commit)."""
    tracer = QueryTracer(flat_app_path)
    
    graph = Graph()
    graph.add_node(Node(
        id="service::create_user",
        type=NodeType.SERVICE,
        label="create_user",
        file_path="app.py",
        line_number=46,
        metadata={}
    ))
    
    tracer.enrich(graph)
    
    node = graph.nodes["service::create_user"]
    operations = node.metadata.get("db_operations", [])
    
    # create_user calls db.session.add() and db.session.commit()
    write_ops = [op for op in operations if op["type"] == "WRITE"]
    assert len(write_ops) >= 2  # add and commit


def test_query_tracer_detects_delete_operations(factory_app_path):
    """Test detection of DELETE operations."""
    tracer = QueryTracer(factory_app_path)
    
    graph = Graph()
    graph.add_node(Node(
        id="service::UserService",
        type=NodeType.SERVICE,
        label="UserService",
        file_path="services/user_service.py",
        line_number=6,
        metadata={"methods": ["delete_user"]}
    ))
    
    tracer.enrich(graph)
    
    node = graph.nodes["service::UserService"]
    operations = node.metadata.get("db_operations", [])
    
    # UserService.delete_user calls db.session.delete()
    delete_ops = [op for op in operations if op["type"] == "DELETE"]
    assert len(delete_ops) > 0


def test_query_tracer_includes_operation_patterns(flat_app_path):
    """Test that operation patterns are included in metadata."""
    tracer = QueryTracer(flat_app_path)
    
    graph = Graph()
    graph.add_node(Node(
        id="service::get_user_by_id",
        type=NodeType.SERVICE,
        label="get_user_by_id",
        file_path="app.py",
        line_number=41,
        metadata={}
    ))
    
    tracer.enrich(graph)
    
    node = graph.nodes["service::get_user_by_id"]
    operations = node.metadata.get("db_operations", [])
    
    # Each operation should have type and pattern
    for op in operations:
        assert "type" in op
        assert op["type"] in ["READ", "WRITE", "DELETE"]


def test_query_tracer_handles_missing_files(flat_app_path):
    """Test that tracer handles missing files gracefully."""
    tracer = QueryTracer(flat_app_path)
    
    graph = Graph()
    graph.add_node(Node(
        id="service::nonexistent",
        type=NodeType.SERVICE,
        label="nonexistent",
        file_path="nonexistent.py",
        line_number=1,
        metadata={}
    ))
    
    # Should not crash
    tracer.enrich(graph)
    
    # Node should still exist
    assert "service::nonexistent" in graph.nodes


def test_query_tracer_works_on_action_nodes(flat_app_path):
    """Test that tracer enriches ACTION nodes as well as SERVICE nodes."""
    tracer = QueryTracer(flat_app_path)
    
    graph = Graph()
    graph.add_node(Node(
        id="action::list_users",
        type=NodeType.ACTION,
        label="list_users",
        file_path="app.py",
        line_number=61,
        metadata={}
    ))
    
    tracer.enrich(graph)
    
    node = graph.nodes["action::list_users"]
    # list_users calls list_all_users() which queries the database
    # But since we're analyzing the view function itself, it may not have direct DB calls
    assert "db_operations" in node.metadata
