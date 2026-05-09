"""Tests for RouteScanner."""

import pytest
from pathlib import Path
from flask_brain.scanners.route_scanner import RouteScanner
from flask_brain.graph import NodeType, EdgeType


@pytest.fixture
def flat_app_path():
    """Path to flat_app fixture."""
    return Path(__file__).parent / "fixtures" / "flat_app"


@pytest.fixture
def factory_app_path():
    """Path to factory_app fixture."""
    return Path(__file__).parent / "fixtures" / "factory_app"


@pytest.fixture
def blueprint_app_path():
    """Path to blueprint_app fixture."""
    return Path(__file__).parent / "fixtures" / "blueprint_app"


def test_route_scanner_flat_app(flat_app_path):
    """Test RouteScanner on flat app."""
    scanner = RouteScanner(flat_app_path)
    nodes, edges = scanner.scan()
    
    # Should find 3 routes
    route_nodes = [n for n in nodes if n.type == NodeType.ROUTE]
    assert len(route_nodes) == 3
    
    # Check route IDs
    route_ids = {n.id for n in route_nodes}
    assert "route::GET /users" in route_ids
    assert "route::GET /users/<int:user_id>" in route_ids
    assert "route::POST /users" in route_ids
    
    # Check route metadata
    get_users_route = next(n for n in route_nodes if n.id == "route::GET /users")
    assert get_users_route.label == "GET /users"
    assert "app.py" in get_users_route.file_path
    assert get_users_route.metadata["methods"] == ["GET"]
    assert get_users_route.metadata["view_function"] == "list_users"


def test_route_scanner_factory_app(factory_app_path):
    """Test RouteScanner on factory app with blueprints."""
    scanner = RouteScanner(factory_app_path)
    nodes, edges = scanner.scan()
    
    # Should find blueprint
    blueprint_nodes = [n for n in nodes if n.type == NodeType.BLUEPRINT]
    assert len(blueprint_nodes) == 1
    assert blueprint_nodes[0].id == "blueprint::users"
    assert blueprint_nodes[0].metadata["url_prefix"] == "/api"
    
    # Should find routes
    route_nodes = [n for n in nodes if n.type == NodeType.ROUTE]
    assert len(route_nodes) >= 4  # GET, POST, PUT, DELETE
    
    # Check that routes have blueprint prefix
    route_ids = {n.id for n in route_nodes}
    assert "route::GET /api/users" in route_ids
    assert "route::POST /api/users" in route_ids
    
    # Check edges from blueprint to routes
    blueprint_edges = [e for e in edges if e.type == EdgeType.REGISTERS_BLUEPRINT]
    assert len(blueprint_edges) >= 1


def test_route_scanner_blueprint_app(blueprint_app_path):
    """Test RouteScanner on blueprint app with multiple blueprints."""
    scanner = RouteScanner(blueprint_app_path)
    nodes, edges = scanner.scan()
    
    # Should find 2 blueprints
    blueprint_nodes = [n for n in nodes if n.type == NodeType.BLUEPRINT]
    assert len(blueprint_nodes) == 2
    
    blueprint_ids = {n.id for n in blueprint_nodes}
    assert "blueprint::users" in blueprint_ids
    assert "blueprint::orders" in blueprint_ids
    
    # Check URL prefixes
    users_bp = next(n for n in blueprint_nodes if n.id == "blueprint::users")
    assert users_bp.metadata["url_prefix"] == "/users"
    
    orders_bp = next(n for n in blueprint_nodes if n.id == "blueprint::orders")
    assert orders_bp.metadata["url_prefix"] == "/orders"
    
    # Should find routes for both blueprints
    route_nodes = [n for n in nodes if n.type == NodeType.ROUTE]
    assert len(route_nodes) >= 6  # 3 user routes + 3 order routes
    
    # Check user routes
    user_route_ids = {n.id for n in route_nodes if "/users" in n.id}
    assert "route::GET /users/" in user_route_ids
    assert "route::POST /users/" in user_route_ids
    
    # Check order routes
    order_route_ids = {n.id for n in route_nodes if "/orders" in n.id}
    assert "route::GET /orders/" in order_route_ids
    assert "route::POST /orders/" in order_route_ids


def test_route_scanner_extracts_view_function_names(flat_app_path):
    """Test that scanner extracts view function names."""
    scanner = RouteScanner(flat_app_path)
    nodes, edges = scanner.scan()
    
    route_nodes = [n for n in nodes if n.type == NodeType.ROUTE]
    
    # All routes should have view_function in metadata
    for route in route_nodes:
        assert "view_function" in route.metadata
        assert route.metadata["view_function"] != ""


def test_route_scanner_handles_multiple_methods(flat_app_path):
    """Test that scanner handles routes with multiple HTTP methods."""
    scanner = RouteScanner(flat_app_path)
    nodes, edges = scanner.scan()
    
    # The /users route accepts both GET and POST
    users_routes = [n for n in nodes if n.type == NodeType.ROUTE and "/users" in n.id]
    
    # Should have separate nodes for GET and POST
    methods = set()
    for route in users_routes:
        methods.update(route.metadata.get("methods", []))
    
    assert "GET" in methods
    assert "POST" in methods
