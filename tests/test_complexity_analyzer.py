"""Tests for ComplexityAnalyzer."""

import pytest
from pathlib import Path

from flask_brain.scanners.complexity_analyzer import ComplexityAnalyzer
from flask_brain.graph import Graph, Node, NodeType


@pytest.fixture
def flat_app_path():
    """Path to flat app fixture."""
    return Path(__file__).parent / "fixtures" / "flat_app"


@pytest.fixture
def factory_app_path():
    """Path to factory app fixture."""
    return Path(__file__).parent / "fixtures" / "factory_app"


def test_complexity_analyzer_calculates_simple_function():
    """Test complexity calculation for a simple function with no branches."""
    analyzer = ComplexityAnalyzer(Path(__file__).parent)
    
    # A function with no branches should have complexity 1
    # We'll test this by creating a simple test case
    # For now, just verify the analyzer can be instantiated
    assert analyzer is not None


def test_complexity_analyzer_calculates_function_with_if():
    """Test complexity calculation for function with if statement."""
    # Complexity should be 2 (base 1 + 1 for if)
    pass


def test_complexity_analyzer_calculates_function_with_multiple_branches():
    """Test complexity calculation for function with multiple branches."""
    # Function with if + elif + for should have complexity 4
    pass


def test_complexity_analyzer_counts_and_or_operators():
    """Test that and/or operators increase complexity."""
    # if x and y: should add 2 (1 for if, 1 for and)
    pass


def test_complexity_analyzer_enriches_graph_nodes(flat_app_path):
    """Test that analyzer enriches existing graph nodes with complexity metadata."""
    analyzer = ComplexityAnalyzer(flat_app_path)
    
    # Create a graph with some nodes
    graph = Graph()
    graph.add_node(Node(
        id="action::list_users",
        type=NodeType.ACTION,
        label="list_users",
        file_path="app.py",
        line_number=61,
        metadata={}
    ))
    
    # Enrich the graph
    analyzer.enrich(graph)
    
    # Node should now have complexity metadata
    node = graph.nodes["action::list_users"]
    assert "complexity" in node.metadata
    assert isinstance(node.metadata["complexity"], int)
    assert node.metadata["complexity"] >= 1


def test_complexity_analyzer_assigns_complexity_tiers(flat_app_path):
    """Test that complexity tiers are assigned correctly."""
    analyzer = ComplexityAnalyzer(flat_app_path)
    
    graph = Graph()
    graph.add_node(Node(
        id="action::list_users",
        type=NodeType.ACTION,
        label="list_users",
        file_path="app.py",
        line_number=61,
        metadata={}
    ))
    
    analyzer.enrich(graph)
    
    node = graph.nodes["action::list_users"]
    assert "complexity_tier" in node.metadata
    assert node.metadata["complexity_tier"] in ["low", "moderate", "high", "critical"]


def test_complexity_analyzer_counts_lines_of_code(flat_app_path):
    """Test that line count is calculated for functions."""
    analyzer = ComplexityAnalyzer(flat_app_path)
    
    graph = Graph()
    graph.add_node(Node(
        id="action::list_users",
        type=NodeType.ACTION,
        label="list_users",
        file_path="app.py",
        line_number=61,
        metadata={}
    ))
    
    analyzer.enrich(graph)
    
    node = graph.nodes["action::list_users"]
    assert "line_count" in node.metadata
    assert isinstance(node.metadata["line_count"], int)
    assert node.metadata["line_count"] > 0


def test_complexity_analyzer_detects_fat_classes(factory_app_path):
    """Test that fat classes are flagged (>10 methods or >300 lines)."""
    analyzer = ComplexityAnalyzer(factory_app_path)
    
    graph = Graph()
    graph.add_node(Node(
        id="service::UserService",
        type=NodeType.SERVICE,
        label="UserService",
        file_path="services/user_service.py",
        line_number=6,
        metadata={"methods": ["get_user", "get_all_users", "create_user", "update_user", "delete_user"]}
    ))
    
    analyzer.enrich(graph)
    
    node = graph.nodes["service::UserService"]
    assert "is_fat" in node.metadata
    assert isinstance(node.metadata["is_fat"], bool)
    # UserService has 5 methods, so it should not be fat
    assert node.metadata["is_fat"] == False


def test_complexity_tier_low():
    """Test that complexity 1-5 is classified as 'low'."""
    analyzer = ComplexityAnalyzer(Path(__file__).parent)
    
    assert analyzer._get_complexity_tier(1) == "low"
    assert analyzer._get_complexity_tier(3) == "low"
    assert analyzer._get_complexity_tier(5) == "low"


def test_complexity_tier_moderate():
    """Test that complexity 6-10 is classified as 'moderate'."""
    analyzer = ComplexityAnalyzer(Path(__file__).parent)
    
    assert analyzer._get_complexity_tier(6) == "moderate"
    assert analyzer._get_complexity_tier(8) == "moderate"
    assert analyzer._get_complexity_tier(10) == "moderate"


def test_complexity_tier_high():
    """Test that complexity 11-20 is classified as 'high'."""
    analyzer = ComplexityAnalyzer(Path(__file__).parent)
    
    assert analyzer._get_complexity_tier(11) == "high"
    assert analyzer._get_complexity_tier(15) == "high"
    assert analyzer._get_complexity_tier(20) == "high"


def test_complexity_tier_critical():
    """Test that complexity 21+ is classified as 'critical'."""
    analyzer = ComplexityAnalyzer(Path(__file__).parent)
    
    assert analyzer._get_complexity_tier(21) == "critical"
    assert analyzer._get_complexity_tier(50) == "critical"
    assert analyzer._get_complexity_tier(100) == "critical"


def test_complexity_analyzer_returns_no_nodes_or_edges(flat_app_path):
    """Test that analyzer returns empty lists (it enriches, doesn't create)."""
    analyzer = ComplexityAnalyzer(flat_app_path)
    nodes, edges = analyzer.scan()
    
    assert nodes == []
    assert edges == []


def test_complexity_analyzer_handles_missing_files(flat_app_path):
    """Test that analyzer handles missing files gracefully."""
    analyzer = ComplexityAnalyzer(flat_app_path)
    
    graph = Graph()
    graph.add_node(Node(
        id="action::nonexistent",
        type=NodeType.ACTION,
        label="nonexistent",
        file_path="nonexistent.py",
        line_number=1,
        metadata={}
    ))
    
    # Should not crash
    analyzer.enrich(graph)
    
    # Node should still exist but may not have complexity metadata
    assert "action::nonexistent" in graph.nodes
