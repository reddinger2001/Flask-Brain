"""Tests for GitChurnAnalyzer."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from flask_brain.scanners.git_churn_analyzer import GitChurnAnalyzer
from flask_brain.graph import Graph, Node, NodeType


@pytest.fixture
def simple_graph(tmp_path):
    """Graph with two nodes at known file paths."""
    g = Graph()
    n1 = Node("action::view_a", NodeType.ACTION, "view_a", "app/views.py", 1,
               metadata={"complexity": 10})
    n2 = Node("service::svc_b", NodeType.SERVICE, "svc_b", "app/services.py", 5,
               metadata={"complexity": 5})
    g.add_node(n1)
    g.add_node(n2)
    return g


def _mock_churn(project_path, file_counts: dict[str, int]):
    """Patch subprocess.run to return a fake git log output."""
    lines = []
    for fpath, count in file_counts.items():
        for _ in range(count):
            lines.append("")       # blank = commit separator (pretty=format: gives empty line)
            lines.append(fpath)    # file touched
    output = "\n".join(lines)

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = output
    return mock_result


def test_git_churn_enriches_churn_count(tmp_path, simple_graph):
    """Nodes should receive churn_count from git log output."""
    analyzer = GitChurnAnalyzer(tmp_path)
    mock_result = _mock_churn(tmp_path, {
        "app/views.py": 8,
        "app/services.py": 3,
    })

    with patch("subprocess.run", return_value=mock_result):
        analyzer.enrich(simple_graph)

    view_node = simple_graph.get_node("action::view_a")
    svc_node = simple_graph.get_node("service::svc_b")

    assert view_node.metadata["churn_count"] == 8
    assert svc_node.metadata["churn_count"] == 3


def test_git_churn_computes_risk_score(tmp_path, simple_graph):
    """risk_score = complexity * churn_count."""
    analyzer = GitChurnAnalyzer(tmp_path)
    mock_result = _mock_churn(tmp_path, {
        "app/views.py": 4,   # complexity=10, risk=40
        "app/services.py": 6, # complexity=5, risk=30
    })

    with patch("subprocess.run", return_value=mock_result):
        analyzer.enrich(simple_graph)

    view_node = simple_graph.get_node("action::view_a")
    svc_node = simple_graph.get_node("service::svc_b")

    assert view_node.metadata["risk_score"] == 40
    assert svc_node.metadata["risk_score"] == 30


def test_git_churn_zero_for_untracked_files(tmp_path, simple_graph):
    """Files not in git log get churn_count=0 and risk_score=0."""
    analyzer = GitChurnAnalyzer(tmp_path)
    mock_result = _mock_churn(tmp_path, {"other/file.py": 10})

    with patch("subprocess.run", return_value=mock_result):
        analyzer.enrich(simple_graph)

    view_node = simple_graph.get_node("action::view_a")
    assert view_node.metadata["churn_count"] == 0
    assert view_node.metadata["risk_score"] == 0


def test_git_churn_handles_no_complexity(tmp_path):
    """Nodes without complexity get risk_score=0 (not an error)."""
    g = Graph()
    n = Node("route::GET /x", NodeType.ROUTE, "GET /x", "routes.py", 1)  # no complexity
    g.add_node(n)

    analyzer = GitChurnAnalyzer(tmp_path)
    mock_result = _mock_churn(tmp_path, {"routes.py": 5})

    with patch("subprocess.run", return_value=mock_result):
        analyzer.enrich(g)

    node = g.get_node("route::GET /x")
    assert node.metadata["churn_count"] == 5
    assert node.metadata["risk_score"] == 0


def test_git_churn_handles_git_not_available(tmp_path, simple_graph):
    """If git is not available, enrich() silently does nothing."""
    import subprocess
    analyzer = GitChurnAnalyzer(tmp_path)

    with patch("subprocess.run", side_effect=FileNotFoundError("git not found")):
        analyzer.enrich(simple_graph)  # must not raise

    view_node = simple_graph.get_node("action::view_a")
    assert "churn_count" not in view_node.metadata


def test_git_churn_handles_non_git_repo(tmp_path, simple_graph):
    """If git returns non-zero (not a repo), enrich() silently does nothing."""
    mock_result = MagicMock()
    mock_result.returncode = 128  # git's "not a git repo" exit code
    mock_result.stdout = ""

    analyzer = GitChurnAnalyzer(tmp_path)
    with patch("subprocess.run", return_value=mock_result):
        analyzer.enrich(simple_graph)

    view_node = simple_graph.get_node("action::view_a")
    assert "churn_count" not in view_node.metadata
