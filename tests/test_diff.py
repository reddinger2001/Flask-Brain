"""Tests for SnapshotManager and DiffEngine."""

import json
import pytest
from pathlib import Path

from flask_brain.graph import Graph, Node, Edge, NodeType, EdgeType
from flask_brain.diff import SnapshotManager, DiffEngine, GraphDiff, NodeChange, EdgeChange


# ── Helpers ───────────────────────────────────────────────────────────────────

def _simple_graph() -> Graph:
    g = Graph()
    g.add_node(Node("route::GET /users", NodeType.ROUTE, "GET /users", "routes.py", 10))
    g.add_node(Node("action::list_users", NodeType.ACTION, "list_users", "actions.py", 5))
    g.add_edge(Edge("route::GET /users", "action::list_users", EdgeType.CALLS))
    return g


def _write_graph(graph_dir: Path, graph: Graph):
    """Write a Graph to graph-all.json in graph_dir."""
    graph_dir.mkdir(parents=True, exist_ok=True)
    with open(graph_dir / "graph-all.json", "w") as f:
        json.dump(graph.to_dict(), f)


# ── SnapshotManager tests ─────────────────────────────────────────────────────

class TestSnapshotManager:

    def test_create_snapshot_returns_id(self, tmp_path):
        brain_dir = tmp_path / ".flask-brain"
        _write_graph(brain_dir, _simple_graph())
        sm = SnapshotManager(tmp_path)
        sid = sm.create_snapshot(label="baseline")
        assert isinstance(sid, str)
        assert len(sid) == 15  # YYYYMMDD-HHMMSS

    def test_create_snapshot_writes_file(self, tmp_path):
        brain_dir = tmp_path / ".flask-brain"
        _write_graph(brain_dir, _simple_graph())
        sm = SnapshotManager(tmp_path)
        sid = sm.create_snapshot()
        snap_file = brain_dir / "snapshots" / f"snapshot-{sid}.json"
        assert snap_file.exists()

    def test_create_snapshot_updates_manifest(self, tmp_path):
        brain_dir = tmp_path / ".flask-brain"
        _write_graph(brain_dir, _simple_graph())
        sm = SnapshotManager(tmp_path)
        sid = sm.create_snapshot(label="v1")
        snaps = sm.list_snapshots()
        assert len(snaps) == 1
        assert snaps[0]["id"] == sid
        assert snaps[0]["label"] == "v1"
        assert snaps[0]["node_count"] == 2
        assert snaps[0]["edge_count"] == 1

    def test_list_snapshots_empty(self, tmp_path):
        brain_dir = tmp_path / ".flask-brain"
        _write_graph(brain_dir, _simple_graph())
        sm = SnapshotManager(tmp_path)
        assert sm.list_snapshots() == []

    def test_load_snapshot_returns_graph(self, tmp_path):
        brain_dir = tmp_path / ".flask-brain"
        g = _simple_graph()
        _write_graph(brain_dir, g)
        sm = SnapshotManager(tmp_path)
        sid = sm.create_snapshot()
        loaded = sm.load_snapshot(sid)
        assert isinstance(loaded, Graph)
        assert loaded.get_node("route::GET /users") is not None

    def test_load_snapshot_unknown_id_raises(self, tmp_path):
        brain_dir = tmp_path / ".flask-brain"
        _write_graph(brain_dir, _simple_graph())
        sm = SnapshotManager(tmp_path)
        with pytest.raises(ValueError, match="not found"):
            sm.load_snapshot("99991231-235959")

    def test_delete_snapshot(self, tmp_path):
        brain_dir = tmp_path / ".flask-brain"
        _write_graph(brain_dir, _simple_graph())
        sm = SnapshotManager(tmp_path)
        sid = sm.create_snapshot()
        sm.delete_snapshot(sid)
        assert sm.list_snapshots() == []
        assert not (brain_dir / "snapshots" / f"snapshot-{sid}.json").exists()

    def test_delete_unknown_snapshot_raises(self, tmp_path):
        brain_dir = tmp_path / ".flask-brain"
        _write_graph(brain_dir, _simple_graph())
        sm = SnapshotManager(tmp_path)
        with pytest.raises(ValueError, match="not found"):
            sm.delete_snapshot("99991231-235959")

    def test_create_snapshot_requires_graph_file(self, tmp_path):
        sm = SnapshotManager(tmp_path)
        with pytest.raises(FileNotFoundError):
            sm.create_snapshot()


# ── DiffEngine tests ──────────────────────────────────────────────────────────

class TestDiffEngine:

    def _engine(self):
        return DiffEngine()

    def test_no_changes_returns_empty_diff(self):
        g = _simple_graph()
        diff = self._engine().compute_diff(g, g, "baseline", "current")
        assert diff.summary["nodes_added"] == 0
        assert diff.summary["nodes_removed"] == 0
        assert diff.summary["nodes_modified"] == 0
        assert diff.summary["edges_added"] == 0
        assert diff.summary["edges_removed"] == 0
        assert diff.node_changes == []
        assert diff.edge_changes == []

    def test_added_node(self):
        baseline = _simple_graph()
        current = _simple_graph()
        current.add_node(Node("service::UserService", NodeType.SERVICE, "UserService", "svc.py", 1))
        diff = self._engine().compute_diff(baseline, current, "b", "c")
        added = [nc for nc in diff.node_changes if nc.change_type == "added"]
        assert len(added) == 1
        assert added[0].node_id == "service::UserService"
        assert added[0].old_node is None
        assert added[0].new_node is not None
        assert diff.summary["nodes_added"] == 1

    def test_removed_node(self):
        baseline = _simple_graph()
        current = Graph()
        current.add_node(Node("route::GET /users", NodeType.ROUTE, "GET /users", "routes.py", 10))
        # action::list_users removed
        diff = self._engine().compute_diff(baseline, current, "b", "c")
        removed = [nc for nc in diff.node_changes if nc.change_type == "removed"]
        assert any(r.node_id == "action::list_users" for r in removed)
        assert diff.summary["nodes_removed"] >= 1

    def test_modified_node_line_number(self):
        baseline = _simple_graph()
        current = _simple_graph()
        current.nodes["route::GET /users"].line_number = 99
        diff = self._engine().compute_diff(baseline, current, "b", "c")
        modified = [nc for nc in diff.node_changes if nc.change_type == "modified"]
        assert len(modified) == 1
        assert modified[0].node_id == "route::GET /users"
        assert "line_number" in modified[0].changes
        assert modified[0].changes["line_number"]["old"] == 10
        assert modified[0].changes["line_number"]["new"] == 99
        assert diff.summary["nodes_modified"] == 1

    def test_modified_node_label(self):
        baseline = _simple_graph()
        current = _simple_graph()
        current.nodes["action::list_users"].label = "list_all_users"
        diff = self._engine().compute_diff(baseline, current, "b", "c")
        modified = [nc for nc in diff.node_changes if nc.change_type == "modified"]
        assert any("label" in nc.changes for nc in modified)

    def test_modified_node_metadata(self):
        baseline = _simple_graph()
        baseline.nodes["action::list_users"].metadata["complexity"] = 5
        current = _simple_graph()
        current.nodes["action::list_users"].metadata["complexity"] = 15
        diff = self._engine().compute_diff(baseline, current, "b", "c")
        modified = [nc for nc in diff.node_changes if nc.change_type == "modified"]
        assert len(modified) == 1
        assert "metadata" in modified[0].changes

    def test_added_edge(self):
        baseline = _simple_graph()
        current = _simple_graph()
        current.add_node(Node("model::User", NodeType.MODEL, "User", "models.py", 1))
        current.add_edge(Edge("action::list_users", "model::User", EdgeType.USES_MODEL))
        diff = self._engine().compute_diff(baseline, current, "b", "c")
        added_edges = [ec for ec in diff.edge_changes if ec.change_type == "added"]
        assert len(added_edges) == 1
        assert added_edges[0].source == "action::list_users"
        assert added_edges[0].target == "model::User"
        assert diff.summary["edges_added"] == 1

    def test_removed_edge(self):
        baseline = _simple_graph()
        current = Graph()
        current.add_node(Node("route::GET /users", NodeType.ROUTE, "GET /users", "routes.py", 10))
        current.add_node(Node("action::list_users", NodeType.ACTION, "list_users", "actions.py", 5))
        # Edge removed
        diff = self._engine().compute_diff(baseline, current, "b", "c")
        removed_edges = [ec for ec in diff.edge_changes if ec.change_type == "removed"]
        assert len(removed_edges) == 1
        assert diff.summary["edges_removed"] == 1

    def test_diff_ids_stored(self):
        g = _simple_graph()
        diff = self._engine().compute_diff(g, g, "snap-001", "snap-002")
        assert diff.baseline_id == "snap-001"
        assert diff.current_id == "snap-002"

    def test_to_dict_round_trips(self):
        baseline = _simple_graph()
        current = _simple_graph()
        current.add_node(Node("service::NewSvc", NodeType.SERVICE, "NewSvc", "s.py", 1))
        diff = self._engine().compute_diff(baseline, current, "b", "c")
        d = diff.to_dict()
        assert "summary" in d
        assert "node_changes" in d
        assert "edge_changes" in d
        assert d["summary"]["nodes_added"] == 1
        # node_changes are dicts
        added = [nc for nc in d["node_changes"] if nc["change_type"] == "added"]
        assert added[0]["node_id"] == "service::NewSvc"
