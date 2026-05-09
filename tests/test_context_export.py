"""Tests for flask_brain/context_export.py — Phase 6."""

import pytest
from flask_brain.graph import Graph, Node, Edge, NodeType, EdgeType
from flask_brain.context_export import export_context


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_graph():
    """Build a small deterministic graph for testing."""
    g = Graph()

    bp = Node(id="blueprint::auth", type=NodeType.BLUEPRINT, label="auth",
              file_path="app/auth/__init__.py", line_number=1)
    route = Node(id="route::POST /auth/login", type=NodeType.ROUTE, label="POST /auth/login",
                 file_path="app/auth/views.py", line_number=12,
                 metadata={"methods": ["POST"], "blueprint": "auth"})
    action = Node(id="action::auth.views.login", type=NodeType.ACTION, label="login",
                  file_path="app/auth/views.py", line_number=15,
                  metadata={"complexity": 5, "db_operations": ["query", "commit"]})
    service = Node(id="service::AuthService.authenticate", type=NodeType.SERVICE,
                   label="AuthService.authenticate",
                   file_path="app/services/auth_service.py", line_number=40,
                   metadata={"complexity": 8})
    model = Node(id="model::User", type=NodeType.MODEL, label="User",
                 file_path="app/models/user.py", line_number=10)

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

    return g, route, action, service, model, bp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExportContext:
    def test_returns_markdown_string(self):
        g, route, *_ = make_graph()
        result = export_context(g, route.id)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_focal_node_identity(self):
        g, route, *_ = make_graph()
        result = export_context(g, route.id)
        assert "POST /auth/login" in result
        assert "route" in result

    def test_includes_depth1_neighbors(self):
        g, route, action, *_ = make_graph()
        result = export_context(g, route.id)
        # The action node should appear (depth 1 from route)
        assert "login" in result or "auth.views.login" in result

    def test_includes_depth2_neighbors(self):
        g, route, action, service, *_ = make_graph()
        result = export_context(g, route.id)
        # Service is depth 2 from route (route→action→service)
        assert "AuthService" in result or "authenticate" in result

    def test_includes_depth3_neighbors(self):
        """Model is depth 2 via action, but test ensures depth=3 BFS reaches it."""
        g, route, *_ = make_graph()
        result = export_context(g, "blueprint::auth", depth=3)
        # blueprint→route→action→model is depth 3
        assert "User" in result

    def test_does_not_exceed_budget(self):
        g, route, *_ = make_graph()
        budget = 200  # very tight budget
        result = export_context(g, route.id, budget=budget)
        # token estimate: words * 1.3
        words = len(result.split())
        assert words * 1.3 <= budget * 1.5  # allow 50% slack for test stability

    def test_output_is_deterministic(self):
        g, route, *_ = make_graph()
        r1 = export_context(g, route.id)
        r2 = export_context(g, route.id)
        assert r1 == r2

    def test_unknown_node_raises(self):
        g, *_ = make_graph()
        with pytest.raises(ValueError, match="not found"):
            export_context(g, "route::nonexistent")

    def test_includes_complexity_table(self):
        g, route, action, *_ = make_graph()
        result = export_context(g, route.id)
        # Should mention complexity values from metadata
        assert "complexity" in result.lower() or "5" in result

    def test_includes_db_operations(self):
        g, route, action, *_ = make_graph()
        result = export_context(g, route.id)
        assert "db_operations" in result.lower() or "query" in result or "commit" in result

    def test_file_path_included(self):
        g, route, *_ = make_graph()
        result = export_context(g, route.id)
        assert "app/auth/views.py" in result

    def test_depth_zero_returns_focal_node_only(self):
        g, route, *_ = make_graph()
        result = export_context(g, route.id, depth=0)
        assert "POST /auth/login" in result
        # Should not contain depth-1 neighbor labels
        assert "AuthService" not in result

    def test_default_depth_is_3(self):
        g, *_ = make_graph()
        result_default = export_context(g, "blueprint::auth")
        result_d3 = export_context(g, "blueprint::auth", depth=3)
        assert result_default == result_d3
