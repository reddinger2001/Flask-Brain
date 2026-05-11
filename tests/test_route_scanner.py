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


# ---------------------------------------------------------------------------
# Decorator detection tests
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_app_path():
    """Path to auth_app fixture — routes with various auth decorator patterns."""
    return Path(__file__).parent / "fixtures" / "auth_app"


def test_route_scanner_detects_login_required(auth_app_path):
    """@login_required must set auth_required=True on the route node."""
    scanner = RouteScanner(auth_app_path)
    nodes, _ = scanner.scan()
    dashboard = next(n for n in nodes if n.type == NodeType.ROUTE and n.label == "GET /dashboard")
    assert dashboard.metadata["auth_required"] is True
    assert "login_required" in dashboard.metadata["decorators"]


def test_route_scanner_detects_admin_required(auth_app_path):
    """@admin_required must set auth_required=True on the route node."""
    scanner = RouteScanner(auth_app_path)
    nodes, _ = scanner.scan()
    admin = next(n for n in nodes if n.type == NodeType.ROUTE and n.label == "GET /admin")
    assert admin.metadata["auth_required"] is True
    assert "admin_required" in admin.metadata["decorators"]


def test_route_scanner_detects_roles_required(auth_app_path):
    """@roles_required(...) must set auth_required=True on the route node."""
    scanner = RouteScanner(auth_app_path)
    nodes, _ = scanner.scan()
    reports = next(n for n in nodes if n.type == NodeType.ROUTE and n.label == "GET /reports")
    assert reports.metadata["auth_required"] is True
    assert "roles_required" in reports.metadata["decorators"]


def test_route_scanner_public_route_has_auth_false(auth_app_path):
    """Route with no auth decorator must have auth_required=False."""
    scanner = RouteScanner(auth_app_path)
    nodes, _ = scanner.scan()
    public = next(n for n in nodes if n.type == NodeType.ROUTE and n.label == "GET /public")
    assert public.metadata["auth_required"] is False
    assert public.metadata["decorators"] == []


def test_route_scanner_stores_all_decorators_regardless_of_auth(auth_app_path):
    """decorators list must contain every non-route decorator, known or unknown."""
    scanner = RouteScanner(auth_app_path)
    nodes, _ = scanner.scan()
    # All protected routes should have their decorator stored
    protected = [n for n in nodes if n.type == NodeType.ROUTE and n.metadata.get("auth_required")]
    for route in protected:
        assert len(route.metadata["decorators"]) > 0, \
            f"Route {route.label} has auth_required=True but empty decorators list"


def test_route_scanner_unknown_decorator_stored_but_not_flagged():
    """An unrecognised decorator must appear in decorators[] but not set auth_required."""
    import tempfile, textwrap
    src = textwrap.dedent("""\
        from flask import Flask, jsonify
        app = Flask(__name__)

        def track_usage(f):
            return f

        @app.route('/metrics')
        @track_usage
        def metrics():
            return jsonify({})
    """)
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "app.py").write_text(src)
        scanner = RouteScanner(Path(tmp))
        nodes, _ = scanner.scan()
        route = next(n for n in nodes if n.type == NodeType.ROUTE)
    assert route.metadata["auth_required"] is False
    assert "track_usage" in route.metadata["decorators"]


# ---------------------------------------------------------------------------
# async def view functions
# ---------------------------------------------------------------------------

def test_route_scanner_detects_async_routes():
    """async def view functions must be scanned the same as sync def."""
    import tempfile, textwrap
    src = textwrap.dedent("""\
        from flask import Blueprint
        bp = Blueprint("tmpl", __name__)

        def login_required(f): return f

        @bp.route("/templates")
        @login_required
        async def list_templates():
            pass

        @bp.route("/templates/new")
        @login_required
        async def new_template():
            pass
    """)
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "views.py").write_text(src)
        scanner = RouteScanner(Path(tmp))
        nodes, _ = scanner.scan()
        routes = [n for n in nodes if n.type == NodeType.ROUTE]
        assert len(routes) == 2, f"Expected 2 routes, got {len(routes)}: {[r.label for r in routes]}"
        for r in routes:
            assert r.metadata["auth_required"] is True, f"{r.label} should be auth_required"
            assert "login_required" in r.metadata["decorators"]


def test_route_scanner_async_no_auth_route():
    """async def route without auth decorator must have auth_required=False."""
    import tempfile, textwrap
    src = textwrap.dedent("""\
        from flask import Flask, jsonify
        app = Flask(__name__)

        @app.route("/health")
        async def health():
            return jsonify({"ok": True})
    """)
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "app.py").write_text(src)
        scanner = RouteScanner(Path(tmp))
        nodes, _ = scanner.scan()
        routes = [n for n in nodes if n.type == NodeType.ROUTE]
        assert len(routes) == 1
        assert routes[0].metadata["auth_required"] is False
        assert routes[0].metadata["decorators"] == []


def test_route_scanner_mixed_sync_async_same_file():
    """Mix of sync and async view functions in one file must all be detected."""
    import tempfile, textwrap
    src = textwrap.dedent("""\
        from flask import Blueprint
        bp = Blueprint("api", __name__)

        def login_required(f): return f

        @bp.route("/sync")
        @login_required
        def sync_view():
            pass

        @bp.route("/async")
        @login_required
        async def async_view():
            pass

        @bp.route("/open")
        async def open_async():
            pass
    """)
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "views.py").write_text(src)
        scanner = RouteScanner(Path(tmp))
        nodes, _ = scanner.scan()
        routes = {n.label: n for n in nodes if n.type == NodeType.ROUTE}
        assert "GET /sync" in routes
        assert "GET /async" in routes
        assert "GET /open" in routes
        assert routes["GET /sync"].metadata["auth_required"] is True
        assert routes["GET /async"].metadata["auth_required"] is True
        assert routes["GET /open"].metadata["auth_required"] is False
