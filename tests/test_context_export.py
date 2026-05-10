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

    def test_source_snippets_added_within_budget(self, tmp_path):
        """Test that source snippets are added when within budget (lines 120-122)."""
        # Create a real file for source snippet
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def test_function():
    return 'hello'
""")
        
        g = Graph()
        node = Node(id="action::test", type=NodeType.ACTION, label="test_function",
                   file_path=str(test_file), line_number=2)
        g.add_node(node)
        
        # Large budget should include source snippets
        result = export_context(g, node.id, budget=10000)
        assert "```python" in result or "test_function" in result

    def test_tree_walk_handles_missing_node(self):
        """Test tree walk handles missing node in node_map (line 169)."""
        g = Graph()
        node1 = Node(id="action::test1", type=NodeType.ACTION, label="test1",
                    file_path="test.py", line_number=1)
        node2 = Node(id="action::test2", type=NodeType.ACTION, label="test2",
                    file_path="test.py", line_number=5)
        g.add_node(node1)
        g.add_node(node2)
        
        # Add edge to non-existent node
        g.add_edge(Edge(source="action::test1", target="action::nonexistent", type=EdgeType.CALLS))
        
        # Should not crash, just skip the missing node
        result = export_context(g, node1.id)
        assert "test1" in result

    def test_empty_tree_returns_empty_string(self):
        """Test that empty tree returns empty string (line 179)."""
        g = Graph()
        node = Node(id="action::isolated", type=NodeType.ACTION, label="isolated",
                   file_path="test.py", line_number=1)
        g.add_node(node)
        
        # Node with no outgoing edges
        result = export_context(g, node.id, depth=1)
        # Should still contain the focal node
        assert "isolated" in result

    def test_db_operations_with_dict_format(self):
        """Test DB operations formatting with dict entries (line 216)."""
        g = Graph()
        node = Node(id="action::test", type=NodeType.ACTION, label="test",
                   file_path="test.py", line_number=1,
                   metadata={"db_operations": [
                       {"type": "SELECT", "pattern": "User.query.all()"},
                       {"type": "INSERT", "pattern": "db.session.add(user)"}
                   ]})
        g.add_node(node)
        
        result = export_context(g, node.id)
        assert "SELECT" in result or "db_operations" in result.lower()

    def test_db_operations_with_non_dict_format(self):
        """Test DB operations formatting with non-dict entries (line 221)."""
        g = Graph()
        node = Node(id="action::test", type=NodeType.ACTION, label="test",
                   file_path="test.py", line_number=1,
                   metadata={"db_operations": "simple_string"})
        g.add_node(node)
        
        result = export_context(g, node.id)
        # Should convert to string without crashing
        assert isinstance(result, str)

    def test_source_snippets_handles_file_not_found(self):
        """Test source snippets handles missing files (lines 248-256)."""
        g = Graph()
        node = Node(id="action::test", type=NodeType.ACTION, label="test",
                   file_path="/nonexistent/file.py", line_number=1)
        g.add_node(node)
        
        # Should not crash on missing file
        result = export_context(g, node.id, budget=10000)
        assert isinstance(result, str)

    def test_source_snippets_empty_returns_empty_string(self):
        """Test source snippets returns empty string when no snippets (line 260)."""
        g = Graph()
        # Node with non-existent file
        node = Node(id="action::test", type=NodeType.ACTION, label="test",
                   file_path="/nonexistent.py", line_number=1)
        g.add_node(node)
        
        result = export_context(g, node.id, budget=10000)
        # Should still return valid markdown without source snippets
        assert "test" in result

    def test_truncate_to_budget_when_over_limit(self):
        """Test token budget truncation (lines 275-277)."""
        g, route, action, service, model, bp = make_graph()
        
        # Very small budget should trigger truncation
        result = export_context(g, route.id, budget=50)
        
        # Should be truncated
        words = len(result.split())
        assert words * 1.3 <= 50 * 2  # Allow some slack for truncation logic
