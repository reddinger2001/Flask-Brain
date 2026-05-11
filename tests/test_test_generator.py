"""Tests for flask_brain/test_generator.py."""

import pytest
from flask_brain.graph import Graph, Node, Edge, NodeType, EdgeType
from flask_brain.test_generator import generate_tests


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_test_graph():
    """Build a small deterministic graph for testing."""
    g = Graph()

    bp = Node(id="blueprint::auth", type=NodeType.BLUEPRINT, label="auth",
              file_path="app/auth/__init__.py", line_number=1)
    route = Node(id="route::POST /auth/login", type=NodeType.ROUTE, label="POST /auth/login",
                 file_path="app/auth/views.py", line_number=12,
                 metadata={"methods": ["POST"], "blueprint": "auth", "url": "/auth/login",
                          "auth_required": False})
    action = Node(id="action::auth.views.login", type=NodeType.ACTION, label="login",
                  file_path="app/auth/views.py", line_number=15,
                  metadata={"complexity": 5, "db_operations": [
                      {"type": "SELECT", "pattern": "User.query.filter_by"},
                      {"type": "UPDATE", "pattern": "db.session.commit"}
                  ]})
    service = Node(id="service::AuthService.authenticate", type=NodeType.SERVICE,
                   label="AuthService.authenticate",
                   file_path="app/services/auth_service.py", line_number=40,
                   metadata={"complexity": 8, "db_operations": [
                       {"type": "SELECT", "pattern": "User.query.get"}
                   ]})
    model = Node(id="model::User", type=NodeType.MODEL, label="User",
                 file_path="app/models/user.py", line_number=10,
                 metadata={"columns": [
                     {"name": "id", "type": "Integer", "nullable": False},
                     {"name": "email", "type": "String", "nullable": False},
                     {"name": "password_hash", "type": "String", "nullable": False},
                 ]})

    for n in [bp, route, action, service, model]:
        g.add_node(n)

    g.add_edge(Edge(source="blueprint::auth", target="route::POST /auth/login",
                    type=EdgeType.REGISTERS_BLUEPRINT))
    g.add_edge(Edge(source="route::POST /auth/login", target="action::auth.views.login",
                    type=EdgeType.CALLS))
    g.add_edge(Edge(source="action::auth.views.login", target="service::AuthService.authenticate",
                    type=EdgeType.CALLS))
    g.add_edge(Edge(source="action::auth.views.login", target="model::User",
                    type=EdgeType.USES_MODEL))
    g.add_edge(Edge(source="service::AuthService.authenticate", target="model::User",
                    type=EdgeType.USES_MODEL))

    return g, bp, route, action, service, model


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGenerateTests:
    def test_returns_dict_with_required_keys(self):
        """Test that generate_tests returns a dict with all required keys."""
        g, bp, *_ = make_test_graph()
        result = generate_tests(g, bp.id)
        
        assert isinstance(result, dict)
        assert "target_id" in result
        assert "target_label" in result
        assert "target_type" in result
        assert "output_path" in result
        assert "tiers" in result
        assert "combined" in result
        assert "stats" in result
        assert "warnings" in result

    def test_blueprint_target_returns_routes_and_services(self):
        """Test generating tests for a blueprint includes routes and services."""
        g, bp, *_ = make_test_graph()
        result = generate_tests(g, bp.id)
        
        assert result["target_type"] == "blueprint"
        assert result["target_label"] == "auth"
        assert "routes" in result["tiers"]
        assert "services" in result["tiers"]
        assert len(result["tiers"]["routes"]) > 0
        assert len(result["tiers"]["services"]) > 0

    def test_service_target_returns_service_tier(self):
        """Test generating tests for a service returns service tier."""
        g, _, _, _, service, _ = make_test_graph()
        result = generate_tests(g, service.id)
        
        assert result["target_type"] == "service"
        assert result["target_label"] == "AuthService.authenticate"
        assert "services" in result["tiers"]
        assert len(result["tiers"]["services"]) > 0

    def test_route_target_returns_route_tier(self):
        """Test generating tests for a route returns route tier."""
        g, _, route, *_ = make_test_graph()
        result = generate_tests(g, route.id)
        
        assert result["target_type"] == "route"
        assert result["target_label"] == "POST /auth/login"
        assert "routes" in result["tiers"]
        assert len(result["tiers"]["routes"]) > 0

    def test_unknown_node_raises_value_error(self):
        """Test that unknown node ID raises ValueError."""
        g, *_ = make_test_graph()
        with pytest.raises(ValueError, match="not found"):
            generate_tests(g, "route::nonexistent")

    def test_combined_field_is_valid_python(self):
        """Test that combined field contains valid Python syntax."""
        g, bp, *_ = make_test_graph()
        result = generate_tests(g, bp.id)
        
        combined = result["combined"]
        assert isinstance(combined, str)
        assert len(combined) > 0
        assert "import pytest" in combined
        assert "def test_" in combined
        
        # Should be syntactically valid (no SyntaxError when compiling)
        try:
            compile(combined, "<string>", "exec")
        except SyntaxError as e:
            pytest.fail(f"Generated code has syntax error: {e}")

    def test_stats_contains_counts(self):
        """Test that stats dict contains expected counts."""
        g, bp, *_ = make_test_graph()
        result = generate_tests(g, bp.id)
        
        stats = result["stats"]
        assert "route_count" in stats
        assert "service_count" in stats
        assert "model_count" in stats
        assert "test_count" in stats
        assert stats["route_count"] >= 1
        assert stats["service_count"] >= 1

    def test_warnings_for_dead_weight(self):
        """Test that dead-weight services generate warnings."""
        g = Graph()
        # Service with no callers
        orphan = Node(id="service::OrphanService.do_nothing", type=NodeType.SERVICE,
                     label="OrphanService.do_nothing",
                     file_path="app/services/orphan.py", line_number=10,
                     metadata={"complexity": 3})
        g.add_node(orphan)
        
        result = generate_tests(g, orphan.id)
        
        # Should have a dead-weight warning
        assert any("dead-weight" in w or "no callers" in w for w in result["warnings"])

    def test_warnings_for_high_complexity(self):
        """Test that high-complexity services generate warnings."""
        g = Graph()
        complex_service = Node(id="service::ComplexService.process", type=NodeType.SERVICE,
                              label="ComplexService.process",
                              file_path="app/services/complex.py", line_number=10,
                              metadata={"complexity": 25})
        g.add_node(complex_service)
        
        result = generate_tests(g, complex_service.id)
        
        # Should have a complexity warning
        assert any("complexity" in w for w in result["warnings"])

    def test_warnings_for_missing_model_columns(self):
        """Test that models without column metadata generate warnings."""
        g = Graph()
        service = Node(id="service::TestService.get", type=NodeType.SERVICE,
                      label="TestService.get",
                      file_path="app/services/test.py", line_number=10,
                      metadata={"complexity": 5})
        model = Node(id="model::Widget", type=NodeType.MODEL, label="Widget",
                    file_path="app/models/widget.py", line_number=10,
                    metadata={})  # No columns
        g.add_node(service)
        g.add_node(model)
        g.add_edge(Edge(source=service.id, target=model.id, type=EdgeType.USES_MODEL))
        
        result = generate_tests(g, service.id)
        
        # Should have a warning about missing column data
        assert any("column" in w.lower() for w in result["warnings"])

    def test_output_path_defaults_to_test_file(self):
        """Test that output_path defaults to a sensible test file name."""
        g, bp, *_ = make_test_graph()
        result = generate_tests(g, bp.id)
        
        output_path = result["output_path"]
        assert output_path.startswith("tests/test_")
        assert output_path.endswith(".py")

    def test_output_path_can_be_specified(self):
        """Test that output_path can be explicitly specified."""
        g, bp, *_ = make_test_graph()
        custom_path = "tests/custom_test_auth.py"
        result = generate_tests(g, bp.id, output_path=custom_path)
        
        assert result["output_path"] == custom_path

    def test_route_test_includes_auth_check(self):
        """Test that routes with auth_required generate auth tests."""
        g = Graph()
        route = Node(id="route::GET /dashboard", type=NodeType.ROUTE, label="GET /dashboard",
                    file_path="app/main/views.py", line_number=10,
                    metadata={"methods": ["GET"], "url": "/dashboard", "auth_required": True})
        g.add_node(route)
        
        result = generate_tests(g, route.id)
        
        combined = result["combined"]
        assert "unauthenticated" in combined.lower() or "401" in combined or "302" in combined

    def test_route_test_includes_post_validation(self):
        """Test that POST routes generate validation tests."""
        g = Graph()
        route = Node(id="route::POST /api/users", type=NodeType.ROUTE, label="POST /api/users",
                    file_path="app/api/views.py", line_number=10,
                    metadata={"methods": ["POST"], "url": "/api/users"})
        g.add_node(route)
        
        result = generate_tests(g, route.id)
        
        combined = result["combined"]
        assert "missing_fields" in combined or "400" in combined or "422" in combined

    def test_route_test_includes_json_check_for_api(self):
        """Test that API routes generate JSON response tests."""
        g = Graph()
        route = Node(id="route::GET /api/status", type=NodeType.ROUTE, label="GET /api/status",
                    file_path="app/api/views.py", line_number=10,
                    metadata={"methods": ["GET"], "url": "/api/status"})
        g.add_node(route)
        
        result = generate_tests(g, route.id)
        
        combined = result["combined"]
        assert "json" in combined.lower()

    def test_service_test_includes_happy_path(self):
        """Test that service tests include happy path test."""
        g, _, _, _, service, _ = make_test_graph()
        result = generate_tests(g, service.id)
        
        combined = result["combined"]
        assert "test_happy_path" in combined

    def test_service_test_includes_not_found(self):
        """Test that service tests include not found test."""
        g, _, _, _, service, _ = make_test_graph()
        result = generate_tests(g, service.id)
        
        combined = result["combined"]
        assert "test_not_found" in combined or "raises" in combined

    def test_service_test_includes_db_persistence_for_write_ops(self):
        """Test that services with write ops generate DB persistence tests."""
        g = Graph()
        service = Node(id="service::UserService.create", type=NodeType.SERVICE,
                      label="UserService.create",
                      file_path="app/services/user.py", line_number=10,
                      metadata={"complexity": 5, "db_operations": [
                          {"type": "INSERT", "pattern": "db.session.add"},
                          {"type": "UPDATE", "pattern": "db.session.commit"}
                      ]})
        g.add_node(service)
        
        result = generate_tests(g, service.id)
        
        combined = result["combined"]
        assert "persists_to_db" in combined or "commit" in combined

    def test_unsupported_node_type_raises_value_error(self):
        """Test that unsupported node types raise ValueError."""
        g = Graph()
        model = Node(id="model::User", type=NodeType.MODEL, label="User",
                    file_path="app/models/user.py", line_number=10)
        g.add_node(model)
        
        with pytest.raises(ValueError, match="Unsupported target type"):
            generate_tests(g, model.id)

    def test_combined_includes_todo_count(self):
        """Test that combined file includes TODO count in header."""
        g, bp, *_ = make_test_graph()
        result = generate_tests(g, bp.id)
        
        combined = result["combined"]
        assert "TODO items remaining:" in combined

    def test_combined_includes_coverage_targets(self):
        """Test that combined file includes coverage targets summary."""
        g, bp, *_ = make_test_graph()
        result = generate_tests(g, bp.id)
        
        combined = result["combined"]
        assert "Coverage targets:" in combined

    def test_combined_includes_timestamp(self):
        """Test that combined file includes generation timestamp."""
        g, bp, *_ = make_test_graph()
        result = generate_tests(g, bp.id)
        
        combined = result["combined"]
        assert "Generated:" in combined

    def test_route_class_name_is_pascal_case(self):
        """Test that route test class names are PascalCase."""
        g = Graph()
        route = Node(id="route::GET /user-profile", type=NodeType.ROUTE, label="GET /user-profile",
                    file_path="app/views.py", line_number=10,
                    metadata={"methods": ["GET"], "url": "/user-profile"})
        g.add_node(route)
        
        result = generate_tests(g, route.id)
        
        combined = result["combined"]
        assert "TestUserProfileRoute" in combined or "class Test" in combined

    def test_service_class_name_is_pascal_case(self):
        """Test that service test class names are PascalCase."""
        g = Graph()
        service = Node(id="service::user_service.get_user", type=NodeType.SERVICE,
                      label="user_service.get_user",
                      file_path="app/services/user.py", line_number=10,
                      metadata={"complexity": 3})
        g.add_node(service)
        
        result = generate_tests(g, service.id)
        
        combined = result["combined"]
        assert "class Test" in combined


# ---------------------------------------------------------------------------
# Bug-fix regression tests
# ---------------------------------------------------------------------------

class TestUrlParamHandling:
    """Regression tests for Issues #1 and #2 — Flask URL param tokens."""

    def _make_graph_with_route(self, url: str, methods=None) -> tuple:
        """Helper: build a minimal graph with one route at the given URL."""
        from flask_brain.graph import Graph, Node, Edge, NodeType, EdgeType
        g = Graph()
        bp = Node(id="blueprint::test", type=NodeType.BLUEPRINT, label="test",
                  file_path="app/test/__init__.py", line_number=1)
        route = Node(
            id=f"route::GET {url}", type=NodeType.ROUTE, label=f"GET {url}",
            file_path="app/test/views.py", line_number=10,
            metadata={
                "methods": methods or ["GET"],
                "url": url,
                "auth_required": False,
                "blueprint": "test",   # required for blueprint_subgraph resolution
            },
        )
        g.add_node(bp)
        g.add_node(route)
        return g, route

    # ── Issue 1: class name must be valid Python ──────────────────────────────

    def test_int_param_in_url_produces_valid_class_name(self):
        """<int:contractor_id> must not appear literally in the class name."""
        import ast, re
        g, _ = self._make_graph_with_route(
            "/contractors/<int:contractor_id>/questionnaires"
        )
        result = generate_tests(g, "blueprint::test")
        combined = result["combined"]
        # Must parse as valid Python — SyntaxError was the original failure
        ast.parse(combined)
        # Every class name found must not contain angle brackets or converter prefixes
        class_names = re.findall(r"^class (\w+)", combined, re.MULTILINE)
        assert class_names, "No class definitions found in generated output"
        for name in class_names:
            assert "<" not in name, f"Angle bracket in class name: {name}"
            assert "int:" not in name, f"Converter prefix in class name: {name}"

    def test_multiple_params_produce_valid_class_name(self):
        """Multiple param tokens in one URL must all be stripped from class name."""
        import ast, re
        g, _ = self._make_graph_with_route(
            "/orgs/<int:org_id>/users/<int:user_id>/edit"
        )
        result = generate_tests(g, "blueprint::test")
        combined = result["combined"]
        ast.parse(combined)
        class_names = re.findall(r"^class (\w+)", combined, re.MULTILINE)
        for name in class_names:
            assert "<" not in name
            assert "int:" not in name

    def test_uuid_param_produces_valid_class_name(self):
        """<uuid:item_id> must not appear literally in the class name."""
        import ast, re
        g, _ = self._make_graph_with_route("/items/<uuid:item_id>")
        result = generate_tests(g, "blueprint::test")
        combined = result["combined"]
        ast.parse(combined)
        class_names = re.findall(r"^class (\w+)", combined, re.MULTILINE)
        for name in class_names:
            assert "uuid:" not in name
            assert "<" not in name

    def test_bare_param_produces_valid_class_name(self):
        """<slug> (no converter) must not appear literally in the class name."""
        import ast, re
        g, _ = self._make_graph_with_route("/<slug>/detail")
        result = generate_tests(g, "blueprint::test")
        combined = result["combined"]
        ast.parse(combined)
        class_names = re.findall(r"^class (\w+)", combined, re.MULTILINE)
        for name in class_names:
            assert "<" not in name

    # ── Issue 2: URL bodies must not contain raw param syntax ─────────────────

    def _client_call_urls(self, combined: str) -> list[str]:
        """Extract URL strings from client.get/post/put/patch/delete calls."""
        import re
        # Match: client.METHOD("URL") or client.METHOD('URL')
        return re.findall(r'client\.\w+\(["\']([^"\']+)["\']', combined)

    def test_int_param_substituted_in_test_body(self):
        """<int:contractor_id> in URL must be replaced with '1' in client calls."""
        g, _ = self._make_graph_with_route(
            "/contractors/<int:contractor_id>/questionnaires"
        )
        result = generate_tests(g, "blueprint::test")
        combined = result["combined"]
        call_urls = self._client_call_urls(combined)
        assert call_urls, "No client calls found in generated output"
        for u in call_urls:
            assert "<" not in u, f"Raw param token in client call URL: {u!r}"
        assert "/contractors/1/questionnaires" in call_urls

    def test_uuid_param_substituted_in_test_body(self):
        """<uuid:item_id> must be replaced with the uuid placeholder in client calls."""
        g, _ = self._make_graph_with_route("/items/<uuid:item_id>")
        result = generate_tests(g, "blueprint::test")
        call_urls = self._client_call_urls(result["combined"])
        assert call_urls
        for u in call_urls:
            assert "<" not in u, f"Raw param token in client call URL: {u!r}"
        assert "/items/00000000-0000-0000-0000-000000000001" in call_urls

    def test_multiple_params_all_substituted(self):
        """Every param token in a URL must be substituted in client calls."""
        g, _ = self._make_graph_with_route(
            "/orgs/<int:org_id>/users/<int:user_id>/edit"
        )
        result = generate_tests(g, "blueprint::test")
        call_urls = self._client_call_urls(result["combined"])
        assert call_urls
        for u in call_urls:
            assert "<" not in u, f"Raw param token in client call URL: {u!r}"
        assert "/orgs/1/users/1/edit" in call_urls

    def test_todo_comments_emitted_for_each_param(self):
        """A TODO comment must be emitted for each substituted param."""
        g, _ = self._make_graph_with_route(
            "/contractors/<int:contractor_id>/questionnaires"
        )
        result = generate_tests(g, "blueprint::test")
        combined = result["combined"]
        assert "# TODO: replace contractor_id=1 with a real fixture ID" in combined

    def test_no_params_produces_no_todo_comments(self):
        """A static URL must not emit any param-substitution TODO comments."""
        g, _ = self._make_graph_with_route("/dashboard")
        result = generate_tests(g, "blueprint::test")
        combined = result["combined"]
        # Param-substitution TODOs have the form "replace <name>=<value> with a real fixture ID"
        assert "replace dashboard" not in combined
        assert "with a real fixture ID" not in combined


# ---------------------------------------------------------------------------
# Bug-fix regression tests — Issues #3–#6
# ---------------------------------------------------------------------------

class TestGeneratedCodeQuality:
    """Regression tests for generator correctness bugs reported after initial release."""

    def _make_route(self, url: str, methods=None, auth_required=False) -> tuple:
        from flask_brain.graph import Graph, Node, NodeType
        g = Graph()
        m = (methods or ["GET"])[0]
        route = Node(
            id=f"route::{m} {url}", type=NodeType.ROUTE, label=f"{m} {url}",
            file_path="app/views.py", line_number=1,
            metadata={"methods": methods or ["GET"], "url": url,
                      "auth_required": auth_required},
        )
        g.add_node(route)
        return g, route

    # ── Bug #3: no app_context wrapper in route tests ──────────────────────────

    def test_route_tests_do_not_use_app_context_wrapper(self):
        """Generated route tests must call client directly — no with app.app_context() wrapper."""
        g, route = self._make_route("/dashboard")
        result = generate_tests(g, route.id)
        combined = result["combined"]
        # app_context wrapper is wrong for route tests; client manages its own context
        assert "with app.app_context():" not in combined

    # ── Bug #4: HTTP method in class name ─────────────────────────────────────

    def test_get_route_class_name_includes_method(self):
        """GET route class name must include 'Get' to avoid collision with POST on same path."""
        g, route = self._make_route("/users")
        result = generate_tests(g, route.id)
        combined = result["combined"]
        assert "class TestGet" in combined

    def test_post_route_class_name_includes_method(self):
        """POST route class name must include 'Post'."""
        g, route = self._make_route("/users", methods=["POST"])
        result = generate_tests(g, route.id)
        combined = result["combined"]
        assert "class TestPost" in combined

    def test_same_url_different_methods_produce_unique_class_names(self):
        """GET and POST on the same URL path must not produce duplicate class names."""
        from flask_brain.graph import Graph, Node, NodeType
        g = Graph()
        get_route = Node(
            id="route::GET /users", type=NodeType.ROUTE, label="GET /users",
            file_path="app/views.py", line_number=1,
            metadata={"methods": ["GET"], "url": "/users", "auth_required": False},
        )
        post_route = Node(
            id="route::POST /users", type=NodeType.ROUTE, label="POST /users",
            file_path="app/views.py", line_number=10,
            metadata={"methods": ["POST"], "url": "/users", "auth_required": False},
        )
        g.add_node(get_route)
        g.add_node(post_route)

        from flask_brain.test_generator import _generate_routes_tier
        code = _generate_routes_tier([get_route, post_route], g)

        import re
        class_names = re.findall(r"^class (\w+)", code, re.MULTILINE)
        assert len(class_names) == len(set(class_names)), \
            f"Duplicate class names found: {class_names}"

    # ── Bug #1: auth-aware test generation ────────────────────────────────────

    def test_auth_required_route_emits_unauthenticated_302_test(self):
        """@login_required route must emit a test asserting 302/401 for unauthed requests."""
        g, route = self._make_route("/dashboard", auth_required=True)
        result = generate_tests(g, route.id)
        combined = result["combined"]
        assert "302" in combined or "401" in combined
        assert "unauthenticated" in combined.lower()

    def test_auth_required_route_emits_authenticated_stub(self):
        """@login_required route must emit an authenticated test stub with a TODO."""
        g, route = self._make_route("/dashboard", auth_required=True)
        result = generate_tests(g, route.id)
        combined = result["combined"]
        assert "authenticated" in combined.lower()
        assert "TODO" in combined

    def test_open_route_emits_direct_200_test(self):
        """Open route must emit a plain 200 test — no auth dance required."""
        g, route = self._make_route("/about")
        result = generate_tests(g, route.id)
        combined = result["combined"]
        assert "status_code == 200" in combined

    # ── Bug #5 (was #3): 999999 for not-found, id=1 only behind a TODO ────────

    def test_service_not_found_uses_999999(self):
        """Not-found service test must use id=999999, not id=1, so a clean DB is safe."""
        from flask_brain.graph import Graph, Node, NodeType
        g = Graph()
        service = Node(
            id="service::UserService.get", type=NodeType.SERVICE,
            label="UserService.get", file_path="app/services/user.py", line_number=1,
            metadata={"complexity": 3},
        )
        g.add_node(service)
        result = generate_tests(g, service.id)
        combined = result["combined"]
        assert "999999" in combined

    # ── No proprietary fixture names in generated output ──────────────────────

    def test_generated_code_has_no_vs_prefix_fixtures(self):
        """Generated code must not reference vs_app, vs_client, vs_db, or vs_tenant."""
        g, route = self._make_route("/users")
        result = generate_tests(g, route.id)
        combined = result["combined"]
        for bad in ("vs_app", "vs_client", "vs_db", "vs_tenant"):
            assert bad not in combined, f"Proprietary fixture name '{bad}' found in generated output"


# ---------------------------------------------------------------------------
# End-to-end: scanner → graph → generator
# ---------------------------------------------------------------------------

class TestScannerToGeneratorIntegration:
    """Verify the full chain: RouteScanner produces metadata that generator uses correctly.

    These tests use a real file on disk, scan it with RouteScanner, build a Graph from
    the result, then call generate_tests() — asserting that auth_required and decorators
    propagate all the way through to the emitted test code.
    """

    def _scan_src(self, src: str):
        """Write src to a temp file, scan it, return (nodes, edges)."""
        import tempfile, textwrap
        from pathlib import Path
        from flask_brain.scanners.route_scanner import RouteScanner
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "views.py").write_text(textwrap.dedent(src))
            scanner = RouteScanner(Path(tmp))
            return scanner.scan()

    def _build_graph(self, nodes, edges):
        from flask_brain.graph import Graph
        g = Graph()
        for n in nodes:
            g.add_node(n)
        for e in edges:
            g.add_edge(e)
        return g

    # ── async def + login_required → auth stubs, NOT open-route 200 ──────────

    def test_async_auth_route_emits_302_test_not_200(self):
        """async def + @login_required must produce test_unauthenticated_returns_302, not assert 200."""
        nodes, edges = self._scan_src("""\
            from flask import Blueprint
            bp = Blueprint("tmpl", __name__)
            def login_required(f): return f

            @bp.route("/templates")
            @login_required
            async def list_templates():
                pass
        """)
        g = self._build_graph(nodes, edges)
        route = next(n for n in g.nodes.values() if n.type.value == "route")
        result = generate_tests(g, route.id)
        combined = result["combined"]
        assert "test_unauthenticated_returns_302" in combined, \
            "async auth route must emit unauthenticated redirect test"
        # Must NOT assert 200 on an authenticated route without logging in
        assert "assert response.status_code == 200" not in combined, \
            "async auth route must not emit a bare 200 assertion"

    def test_async_open_route_emits_200_test(self):
        """async def without auth decorator must produce a runnable assert 200 test."""
        nodes, edges = self._scan_src("""\
            from flask import Flask, jsonify
            app = Flask(__name__)

            @app.route("/health")
            async def health():
                return jsonify({"ok": True})
        """)
        g = self._build_graph(nodes, edges)
        route = next(n for n in g.nodes.values() if n.type.value == "route")
        result = generate_tests(g, route.id)
        combined = result["combined"]
        assert "status_code == 200" in combined
        assert "test_unauthenticated_returns_302" not in combined

    def test_async_auth_route_auth_required_flag_propagates(self):
        """auth_required=True must be present in graph metadata after scanning async def."""
        nodes, edges = self._scan_src("""\
            from flask import Blueprint
            bp = Blueprint("tmpl", __name__)
            def login_required(f): return f

            @bp.route("/templates/new")
            @login_required
            async def new_template():
                pass
        """)
        g = self._build_graph(nodes, edges)
        route = next(n for n in g.nodes.values() if n.type.value == "route")
        assert route.metadata["auth_required"] is True
        assert "login_required" in route.metadata["decorators"]

    def test_mixed_sync_async_routes_both_generate_correctly(self):
        """Mix of sync+async routes in one scan must each get the right generated output."""
        nodes, edges = self._scan_src("""\
            from flask import Blueprint
            bp = Blueprint("api", __name__)
            def login_required(f): return f

            @bp.route("/sync-auth")
            @login_required
            def sync_protected():
                pass

            @bp.route("/async-auth")
            @login_required
            async def async_protected():
                pass

            @bp.route("/open")
            async def open_view():
                pass
        """)
        g = self._build_graph(nodes, edges)
        routes = {n.label: n for n in g.nodes.values() if n.type.value == "route"}

        for label in ("GET /sync-auth", "GET /async-auth"):
            result = generate_tests(g, routes[label].id)
            combined = result["combined"]
            assert "test_unauthenticated_returns_302" in combined, \
                f"{label} must emit redirect test"

        open_result = generate_tests(g, routes["GET /open"].id)
        assert "status_code == 200" in open_result["combined"]
        assert "test_unauthenticated_returns_302" not in open_result["combined"]


# ---------------------------------------------------------------------------
# Source-based model inference
# ---------------------------------------------------------------------------

class TestInferModelsFromSource:
    """_infer_models_from_source reads a service file and extracts model names
    from import statements — filling the gap when graph edges are incomplete."""

    def _make_service_node(self, tmp_path, source: str) -> "Node":
        """Write source to a service file and return a Node pointing at it."""
        svc_file = tmp_path / "services" / "my_service.py"
        svc_file.parent.mkdir(parents=True, exist_ok=True)
        svc_file.write_text(source)
        from flask_brain.graph import Node, NodeType
        return Node(
            id="service::MyService",
            type=NodeType.SERVICE,
            label="MyService",
            file_path="services/my_service.py",
            line_number=1,
        )

    def test_extracts_model_names_from_model_imports(self, tmp_path):
        """CamelCase names imported from a models module are returned."""
        from flask_brain.test_generator import _infer_models_from_source
        node = self._make_service_node(tmp_path, (
            "from app.models.evidence_file import EvidenceFile\n"
            "from app.models.compliance_record import ComplianceRecord\n"
            "from app.utils.helpers import some_helper\n"  # should be ignored
            "\ndef upload(): pass\n"
        ))
        result = _infer_models_from_source(node, tmp_path)
        names = [r[0] for r in result]
        assert "EvidenceFile" in names
        assert "ComplianceRecord" in names
        assert "some_helper" not in names  # not from a models module

    def test_ignores_non_model_imports(self, tmp_path):
        """Names imported from non-models modules are not included."""
        from flask_brain.test_generator import _infer_models_from_source
        node = self._make_service_node(tmp_path, (
            "from flask import current_app\n"
            "from app.services.audit import audit_service\n"
            "from app.models.user import User\n"
        ))
        result = _infer_models_from_source(node, tmp_path)
        names = [r[0] for r in result]
        assert names == ["User"]

    def test_handles_aliased_imports(self, tmp_path):
        """Import aliases (as X) are recorded under the alias name."""
        from flask_brain.test_generator import _infer_models_from_source
        node = self._make_service_node(tmp_path, (
            "from app.models.evidence_file import EvidenceFile as EF\n"
        ))
        result = _infer_models_from_source(node, tmp_path)
        names = [r[0] for r in result]
        assert "EF" in names
        assert "EvidenceFile" not in names

    def test_returns_empty_for_missing_file(self, tmp_path):
        """Returns empty list gracefully when file_path doesn't exist."""
        from flask_brain.test_generator import _infer_models_from_source
        from flask_brain.graph import Node, NodeType
        node = Node(
            id="service::Ghost",
            type=NodeType.SERVICE,
            label="Ghost",
            file_path="services/does_not_exist.py",
            line_number=1,
        )
        result = _infer_models_from_source(node, tmp_path)
        assert result == []

    def test_generate_service_class_includes_inferred_models(self, tmp_path):
        """generate_tests emits model names and import hints in the scaffold."""
        from flask_brain.graph import Graph, Node, NodeType
        from flask_brain.test_generator import generate_tests

        svc_file = tmp_path / "services" / "evidence_service.py"
        svc_file.parent.mkdir(parents=True, exist_ok=True)
        svc_file.write_text(
            "from app.models.evidence_file import EvidenceFile\n"
            "from app.models.compliance_record import ComplianceRecord\n"
            "\nclass EvidenceService:\n"
            "    def upload(self): pass\n"
        )

        g = Graph()
        svc = Node(
            id="service::EvidenceService",
            type=NodeType.SERVICE,
            label="EvidenceService",
            file_path="services/evidence_service.py",
            line_number=4,
            metadata={"methods": ["upload"], "db_operations": [{"type": "WRITE", "pattern": "db.session.add()"}]},
        )
        g.add_node(svc)

        result = generate_tests(g, "service::EvidenceService", project_root=tmp_path)
        combined = result["combined"]

        assert "EvidenceFile" in combined, "EvidenceFile should appear in scaffold"
        assert "ComplianceRecord" in combined, "ComplianceRecord should appear in scaffold"
        assert "from app.models.evidence_file import EvidenceFile" in combined
        assert "from app.models.compliance_record import ComplianceRecord" in combined
        # DB example hint should use the real model name, not 'MyModel'
        assert "EvidenceFile.query.count()" in combined or "ComplianceRecord.query.count()" in combined
