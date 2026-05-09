"""Snapshot management and graph diff engine for Flask Brain."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask_brain.graph import Graph


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class NodeChange:
    node_id: str
    change_type: str  # "added" | "removed" | "modified"
    old_node: dict[str, Any] | None
    new_node: dict[str, Any] | None
    changes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "change_type": self.change_type,
            "old_node": self.old_node,
            "new_node": self.new_node,
            "changes": self.changes,
        }


@dataclass
class EdgeChange:
    source: str
    target: str
    edge_type: str
    change_type: str  # "added" | "removed"
    old_edge: dict[str, Any] | None
    new_edge: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "edge_type": self.edge_type,
            "change_type": self.change_type,
            "old_edge": self.old_edge,
            "new_edge": self.new_edge,
        }


@dataclass
class GraphDiff:
    baseline_id: str
    current_id: str
    summary: dict[str, int]
    node_changes: list[NodeChange]
    edge_changes: list[EdgeChange]

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_id": self.baseline_id,
            "current_id": self.current_id,
            "summary": self.summary,
            "node_changes": [nc.to_dict() for nc in self.node_changes],
            "edge_changes": [ec.to_dict() for ec in self.edge_changes],
        }


# ── DiffEngine ────────────────────────────────────────────────────────────────

class DiffEngine:
    """Computes a structural diff between two Graph objects."""

    _COMPARABLE_FIELDS = ("label", "file_path", "line_number", "type")

    def compute_diff(
        self,
        baseline: Graph,
        current: Graph,
        baseline_id: str,
        current_id: str = "current",
    ) -> GraphDiff:
        """Compare two Graph objects and return a GraphDiff.

        Args:
            baseline: The older/reference graph.
            current:  The newer/comparison graph.
            baseline_id: Snapshot ID of the baseline.
            current_id:  Snapshot ID of the current graph (or "current").

        Returns:
            GraphDiff with all added/removed/modified nodes and edges.
        """
        baseline_nodes = {nid: n.to_dict() for nid, n in baseline.nodes.items()}
        current_nodes = {nid: n.to_dict() for nid, n in current.nodes.items()}

        node_changes: list[NodeChange] = []

        # Added and modified nodes
        for nid, cur_node in current_nodes.items():
            if nid not in baseline_nodes:
                node_changes.append(NodeChange(
                    node_id=nid,
                    change_type="added",
                    old_node=None,
                    new_node=cur_node,
                ))
            else:
                field_changes = self._detect_node_changes(baseline_nodes[nid], cur_node)
                if field_changes:
                    node_changes.append(NodeChange(
                        node_id=nid,
                        change_type="modified",
                        old_node=baseline_nodes[nid],
                        new_node=cur_node,
                        changes=field_changes,
                    ))

        # Removed nodes
        for nid, base_node in baseline_nodes.items():
            if nid not in current_nodes:
                node_changes.append(NodeChange(
                    node_id=nid,
                    change_type="removed",
                    old_node=base_node,
                    new_node=None,
                ))

        # Edge diffs
        def _edge_key(e_dict: dict) -> tuple[str, str, str]:
            return (e_dict["source"], e_dict["target"], e_dict["type"])

        baseline_edges = {_edge_key(e.to_dict()): e.to_dict() for e in baseline.edges}
        current_edges = {_edge_key(e.to_dict()): e.to_dict() for e in current.edges}

        edge_changes: list[EdgeChange] = []

        for key, cur_edge in current_edges.items():
            if key not in baseline_edges:
                edge_changes.append(EdgeChange(
                    source=key[0], target=key[1], edge_type=key[2],
                    change_type="added", old_edge=None, new_edge=cur_edge,
                ))

        for key, base_edge in baseline_edges.items():
            if key not in current_edges:
                edge_changes.append(EdgeChange(
                    source=key[0], target=key[1], edge_type=key[2],
                    change_type="removed", old_edge=base_edge, new_edge=None,
                ))

        summary = {
            "nodes_added":   sum(1 for nc in node_changes if nc.change_type == "added"),
            "nodes_removed": sum(1 for nc in node_changes if nc.change_type == "removed"),
            "nodes_modified":sum(1 for nc in node_changes if nc.change_type == "modified"),
            "edges_added":   sum(1 for ec in edge_changes if ec.change_type == "added"),
            "edges_removed": sum(1 for ec in edge_changes if ec.change_type == "removed"),
        }

        return GraphDiff(
            baseline_id=baseline_id,
            current_id=current_id,
            summary=summary,
            node_changes=node_changes,
            edge_changes=edge_changes,
        )

    def _detect_node_changes(
        self,
        old: dict[str, Any],
        new: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Return dict of changed fields between two node dicts."""
        changes: dict[str, Any] = {}
        for f in self._COMPARABLE_FIELDS:
            old_val = old.get(f)
            new_val = new.get(f)
            if old_val != new_val:
                changes[f] = {"old": old_val, "new": new_val}

        old_meta = old.get("metadata") or {}
        new_meta = new.get("metadata") or {}
        if old_meta != new_meta:
            changes["metadata"] = {"old": old_meta, "new": new_meta}

        return changes


# ── SnapshotManager ───────────────────────────────────────────────────────────

class SnapshotManager:
    """Manages named snapshots of graph-all.json inside .flask-brain/snapshots/."""

    def __init__(self, project_path: Path | str):
        self.project_path = Path(project_path)
        self.brain_dir = self.project_path / ".flask-brain"
        self.snapshots_dir = self.brain_dir / "snapshots"
        self.manifest_file = self.snapshots_dir / "manifest.json"

        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        if not self.manifest_file.exists():
            self._save_manifest({"snapshots": []})

    # ── Public API ────────────────────────────────────────────────────────────

    def create_snapshot(self, label: str | None = None) -> str:
        """Copy the current graph-all.json into a new snapshot.

        Returns:
            Snapshot ID string (YYYYMMDD-HHMMSS).

        Raises:
            FileNotFoundError: If graph-all.json does not exist.
        """
        graph_file = self.brain_dir / "graph-all.json"
        if not graph_file.exists():
            raise FileNotFoundError(
                "No graph-all.json found. Run 'flask-brain scan' first."
            )

        snapshot_id = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
        snapshot_filename = f"snapshot-{snapshot_id}.json"
        snapshot_path = self.snapshots_dir / snapshot_filename

        shutil.copy(graph_file, snapshot_path)

        with open(graph_file) as f:
            graph_data = json.load(f)

        manifest = self._load_manifest()
        manifest["snapshots"].append({
            "id": snapshot_id,
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "label": label,
            "node_count": len(graph_data.get("nodes", [])),
            "edge_count": len(graph_data.get("edges", [])),
            "file_path": f"snapshots/{snapshot_filename}",
        })
        self._save_manifest(manifest)
        return snapshot_id

    def list_snapshots(self) -> list[dict[str, Any]]:
        """Return list of snapshot metadata dicts, oldest first."""
        return self._load_manifest()["snapshots"]

    def load_snapshot(self, snapshot_id: str) -> Graph:
        """Load a snapshot by ID and return a Graph object.

        Raises:
            ValueError: If snapshot_id is not in the manifest.
        """
        meta = self._find_snapshot(snapshot_id)
        snapshot_path = self.brain_dir / meta["file_path"]
        with open(snapshot_path) as f:
            data = json.load(f)
        return Graph.from_dict(data)

    def delete_snapshot(self, snapshot_id: str) -> None:
        """Delete a snapshot by ID.

        Raises:
            ValueError: If snapshot_id is not in the manifest.
        """
        meta = self._find_snapshot(snapshot_id)
        snapshot_path = self.brain_dir / meta["file_path"]
        snapshot_path.unlink(missing_ok=True)

        manifest = self._load_manifest()
        manifest["snapshots"] = [s for s in manifest["snapshots"] if s["id"] != snapshot_id]
        self._save_manifest(manifest)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _find_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        manifest = self._load_manifest()
        for s in manifest["snapshots"]:
            if s["id"] == snapshot_id:
                return s
        raise ValueError(f"Snapshot '{snapshot_id}' not found.")

    def _load_manifest(self) -> dict[str, Any]:
        with open(self.manifest_file) as f:
            return json.load(f)

    def _save_manifest(self, manifest: dict[str, Any]) -> None:
        self.manifest_file.write_text(json.dumps(manifest, indent=2))
