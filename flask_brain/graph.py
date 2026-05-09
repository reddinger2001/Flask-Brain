"""Graph data model for Flask Brain."""

from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any
from datetime import datetime, timezone
import json


class NodeType(str, Enum):
    """Types of nodes in the architecture graph."""
    ROUTE = "route"
    BLUEPRINT = "blueprint"
    ACTION = "action"
    SERVICE = "service"
    MODEL = "model"
    TASK = "task"
    RELATIONSHIP = "relationship"


class EdgeType(str, Enum):
    """Types of edges connecting nodes."""
    CALLS = "calls"
    USES_MODEL = "uses_model"
    HAS_RELATIONSHIP = "has_relationship"
    DISPATCHES_TASK = "dispatches_task"
    REGISTERS_BLUEPRINT = "registers_blueprint"


@dataclass
class Node:
    """A node in the architecture graph."""
    id: str
    type: NodeType
    label: str
    file_path: str
    line_number: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert node to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "label": self.label,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Node":
        """Create node from dictionary."""
        return cls(
            id=data["id"],
            type=NodeType(data["type"]),
            label=data["label"],
            file_path=data["file_path"],
            line_number=data["line_number"],
            metadata=data.get("metadata", {}),
        )


@dataclass
class Edge:
    """An edge connecting two nodes in the graph."""
    source: str
    target: str
    type: EdgeType
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert edge to dictionary."""
        return {
            "source": self.source,
            "target": self.target,
            "type": self.type.value,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Edge":
        """Create edge from dictionary."""
        return cls(
            source=data["source"],
            target=data["target"],
            type=EdgeType(data["type"]),
            metadata=data.get("metadata", {}),
        )


class Graph:
    """Architecture graph containing nodes and edges."""

    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []

    def add_node(self, node: Node) -> None:
        """Add a node to the graph. If node with same ID exists, merge metadata."""
        if node.id in self.nodes:
            # Merge metadata from new node into existing node
            existing = self.nodes[node.id]
            existing.metadata.update(node.metadata)
        else:
            self.nodes[node.id] = node

    def add_edge(self, edge: Edge) -> None:
        """Add an edge to the graph. Silently drops edges with missing endpoints or duplicates."""
        # Drop dangling edges — Cytoscape crashes on nonexistent source/target
        if edge.source not in self.nodes or edge.target not in self.nodes:
            return
        # Deduplicate
        for existing_edge in self.edges:
            if (existing_edge.source == edge.source and
                    existing_edge.target == edge.target and
                    existing_edge.type == edge.type):
                return
        self.edges.append(edge)

    def get_node(self, node_id: str) -> Node | None:
        """Get a node by ID."""
        return self.nodes.get(node_id)

    def get_edges_from(self, node_id: str) -> list[Edge]:
        """Get all edges originating from a node."""
        return [e for e in self.edges if e.source == node_id]

    def get_edges_to(self, node_id: str) -> list[Edge]:
        """Get all edges pointing to a node."""
        return [e for e in self.edges if e.target == node_id]

    def to_dict(self) -> dict[str, Any]:
        """Convert graph to dictionary."""
        return {
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Graph":
        """Create graph from dictionary."""
        graph = cls()
        for node_data in data.get("nodes", []):
            graph.add_node(Node.from_dict(node_data))
        for edge_data in data.get("edges", []):
            graph.add_edge(Edge.from_dict(edge_data))
        return graph

    def write(self, output_dir: Path) -> None:
        """Write graph to JSON files in output directory."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Write manifest
        manifest = {
            "project_name": "scanned_project",
            "scan_timestamp": datetime.now(timezone.utc).isoformat(),
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "node_types": self._count_node_types(),
        }
        with open(output_dir / "manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)

        # Write full graph
        with open(output_dir / "graph-all.json", "w") as f:
            json.dump(self.to_dict(), f, indent=2)

        # Write route-level subgraph
        route_graph = self._filter_by_node_type(NodeType.ROUTE)
        with open(output_dir / "graph-routes.json", "w") as f:
            json.dump(route_graph.to_dict(), f, indent=2)

        # Write per-route subgraphs
        for node_id, node in self.nodes.items():
            if node.type == NodeType.ROUTE:
                route_graph = self._subgraph_from_node(node_id, depth=3)
                safe_id = (node_id.replace("::", "_").replace("/", "_")
                           .replace(" ", "_").replace("<", "").replace(">", "")
                           .replace(":", "_"))
                with open(output_dir / f"graph-{safe_id}.json", "w") as f:
                    json.dump(route_graph.to_dict(), f, indent=2)

    def _count_node_types(self) -> dict[str, int]:
        """Count nodes by type."""
        counts = {}
        for node in self.nodes.values():
            type_name = node.type.value
            counts[type_name] = counts.get(type_name, 0) + 1
        return counts

    def _filter_by_node_type(self, node_type: NodeType) -> "Graph":
        """Create a subgraph containing only nodes of a specific type."""
        subgraph = Graph()
        for node in self.nodes.values():
            if node.type == node_type:
                subgraph.add_node(node)
        return subgraph

    def impact_subgraph(self, node_id: str, depth: int = 5) -> "Graph":
        """Return the reverse-walk subgraph: all nodes that depend on node_id.

        Walks edges BACKWARDS from node_id — i.e. finds every node that has a
        path TO node_id. This answers: "what breaks if this node changes?"

        Args:
            node_id: Starting node ID.
            depth:   Maximum hop distance to traverse (default 5).

        Returns:
            A new Graph containing:
            - The starting node
            - All ancestor nodes within 'depth' hops
            - All edges that connect those ancestors to node_id (and to each other)

        Raises:
            ValueError: If node_id does not exist in the graph.
        """
        if node_id not in self.nodes:
            raise ValueError(f"Node '{node_id}' not found in graph")

        # Build reverse adjacency: target → list of (source, edge)
        reverse: dict[str, list[tuple[str, Edge]]] = {}
        for edge in self.edges:
            reverse.setdefault(edge.target, []).append((edge.source, edge))

        subgraph = Graph()
        visited: set[str] = set()
        queue: list[tuple[str, int]] = [(node_id, 0)]

        while queue:
            current_id, current_depth = queue.pop(0)
            if current_id in visited or current_depth > depth:
                continue
            visited.add(current_id)
            node = self.get_node(current_id)
            if node:
                subgraph.add_node(node)

            if current_depth >= depth:
                continue  # Don't walk further; don't add nodes at depth+1

            for source_id, edge in reverse.get(current_id, []):
                if source_id not in visited:
                    queue.append((source_id, current_depth + 1))
                # Only include the edge+source if source will be within depth
                # (it'll be added when dequeued and visited)
                # We add the edge now but the source node will be added on its own visit
                source_node = self.get_node(source_id)
                if source_node and source_id not in visited:
                    # Tentatively add edge; source node added when visited
                    subgraph.add_edge(edge)

        return subgraph

    def blind_spots(
        self,
        node_types: set[NodeType] | None = None,
    ) -> list[Node]:
        """Return nodes that make DB calls but have no resolved model edges.

        These are ACTION, SERVICE, or TASK nodes where:
          - metadata["db_op_count"] > 0  (query_tracer detected DB operations)
          - BUT no outgoing edge of type USES_MODEL exists

        This indicates the scanner detected database activity but could not
        resolve the model name — a coverage gap worth highlighting.

        Args:
            node_types: Set of NodeType values to check. Defaults to
                        {ACTION, SERVICE, TASK}.

        Returns:
            Sorted list of Node objects matching the blind-spot criteria.
        """
        if node_types is None:
            node_types = {NodeType.ACTION, NodeType.SERVICE, NodeType.TASK}

        # Build set of node IDs that have at least one USES_MODEL outgoing edge
        has_model_edge: set[str] = {
            e.source for e in self.edges if e.type == EdgeType.USES_MODEL
        }

        result = []
        for node in self.nodes.values():
            if node.type not in node_types:
                continue
            db_ops = node.metadata.get("db_op_count", 0) or 0
            if db_ops > 0 and node.id not in has_model_edge:
                result.append(node)

        result.sort(key=lambda n: (-(n.metadata.get("db_op_count") or 0), n.label))
        return result

    def dead_weight(
        self,
        node_types: set[NodeType] | None = None,
    ) -> list[Node]:
        """Return nodes that have NO incoming edges (i.e. nothing calls them).

        By default checks SERVICE, ACTION, and TASK nodes.
        ROUTE nodes are deliberately excluded — they are entry-points by design.
        MODEL and BLUEPRINT nodes are excluded — they are referenced by type, not called.

        Args:
            node_types: Set of NodeType values to check. Defaults to
                        {SERVICE, ACTION, TASK}.

        Returns:
            Sorted list of Node objects with zero incoming edges.
        """
        if node_types is None:
            node_types = {NodeType.SERVICE, NodeType.ACTION, NodeType.TASK}

        # Build set of all node IDs that appear as an edge TARGET
        targeted: set[str] = {e.target for e in self.edges}

        result = []
        for node in self.nodes.values():
            if node.type in node_types and node.id not in targeted:
                result.append(node)

        result.sort(key=lambda n: (n.type.value, n.label))
        return result

    def _subgraph_from_node(self, start_node_id: str, depth: int = 3) -> "Graph":
        """Create a subgraph by traversing from a starting node up to a given depth."""
        subgraph = Graph()
        visited = set()
        queue = [(start_node_id, 0)]

        while queue:
            node_id, current_depth = queue.pop(0)
            if node_id in visited or current_depth > depth:
                continue

            visited.add(node_id)
            node = self.get_node(node_id)
            if node:
                subgraph.add_node(node)

            # Add outgoing edges and their targets
            for edge in self.get_edges_from(node_id):
                if edge.target not in visited and current_depth < depth:
                    queue.append((edge.target, current_depth + 1))
                # Only add the edge after both endpoints are (or will be) in the subgraph
                target_node = self.get_node(edge.target)
                if target_node:
                    subgraph.add_node(target_node)
                    subgraph.add_edge(edge)

        return subgraph


class GraphBuilder:
    """Builds a unified graph from multiple scanner outputs."""

    def __init__(self):
        self.graph = Graph()

    def add_scanner_output(self, nodes: list[Node], edges: list[Edge]) -> None:
        """Add nodes and edges from a scanner to the graph."""
        for node in nodes:
            self.graph.add_node(node)
        for edge in edges:
            self.graph.add_edge(edge)

    def build(self, project_path: Path) -> Graph:
        """Build complete graph by running all scanners on a project."""
        from flask_brain.scanners.route_scanner import RouteScanner
        from flask_brain.scanners.model_scanner import ModelScanner
        from flask_brain.scanners.view_tracer import ViewFunctionTracer
        from flask_brain.scanners.service_scanner import ServiceScanner
        from flask_brain.scanners.celery_scanner import CeleryTaskScanner
        from flask_brain.scanners.complexity_analyzer import ComplexityAnalyzer
        from flask_brain.scanners.query_tracer import QueryTracer
        
        # Run all scanners that create nodes and edges
        scanners = [
            RouteScanner(project_path),
            ModelScanner(project_path),
            ViewFunctionTracer(project_path),
            ServiceScanner(project_path),
            CeleryTaskScanner(project_path),
        ]
        
        for scanner in scanners:
            nodes, edges = scanner.scan()
            self.add_scanner_output(nodes, edges)
        
        # Enrich nodes with complexity and query metadata
        complexity_analyzer = ComplexityAnalyzer(project_path)
        complexity_analyzer.enrich(self.graph)
        
        query_tracer = QueryTracer(project_path)
        query_tracer.enrich(self.graph)
        
        return self.graph

    def get_graph(self) -> Graph:
        """Get the current graph."""
        return self.graph
