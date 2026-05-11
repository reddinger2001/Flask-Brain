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
    PROPERTY = "property"


class EdgeType(str, Enum):
    """Types of edges connecting nodes."""
    CALLS = "calls"
    USES_MODEL = "uses_model"
    HAS_RELATIONSHIP = "has_relationship"
    DISPATCHES_TASK = "dispatches_task"
    REGISTERS_BLUEPRINT = "registers_blueprint"
    DEFINES_PROPERTY = "defines_property"
    READS_PROPERTY = "reads_property"
    WRITES_PROPERTY = "writes_property"


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

    def search(self, query: str, limit: int = 100) -> list[Node]:
        """Search nodes using free-text and/or predicate syntax.

        Predicate syntax (space-separated, all must match — AND logic):
            type=route          node.type equals "route"
            model=Contractor    node has a USES_MODEL edge to model::Contractor
            blueprint=auth      node.metadata["blueprint"] equals "auth"
            complexity>20       node.metadata["complexity"] > 20
            complexity<10       node.metadata["complexity"] < 10
            complexity=15       node.metadata["complexity"] == 15

        Any token that is NOT a predicate is treated as a free-text term that
        must appear in node.label or node.file_path (case-insensitive substring).

        Args:
            query:  The search string.
            limit:  Maximum number of results to return.

        Returns:
            List of matching Node objects sorted by label.
        """
        import re

        tokens = query.strip().split()
        if not tokens:
            return []

        # Pre-build: set of (source, target_label) for uses_model edges
        model_callers: dict[str, set[str]] = {}
        for edge in self.edges:
            if edge.type == EdgeType.USES_MODEL:
                # target looks like "model::ModelName"
                model_name = edge.target.split("::", 1)[-1].lower()
                model_callers.setdefault(edge.source, set()).add(model_name)

        predicate_re = re.compile(
            r'^(type|model|blueprint|complexity)(=|>|<)(.+)$', re.IGNORECASE
        )

        predicates = []
        text_terms = []
        for token in tokens:
            m = predicate_re.match(token)
            if m:
                predicates.append((m.group(1).lower(), m.group(2), m.group(3).lower()))
            else:
                text_terms.append(token.lower())

        results = []
        for node in self.nodes.values():
            # ── Free-text filter ────────────────────────────────────────────
            searchable = (node.label + " " + node.file_path).lower()
            if text_terms and not all(t in searchable for t in text_terms):
                continue

            # ── Predicate filter ────────────────────────────────────────────
            match = True
            for field, op, value in predicates:
                if field == "type":
                    if op == "=" and node.type.value.lower() != value:
                        match = False; break
                elif field == "model":
                    callers = model_callers.get(node.id, set())
                    if op == "=" and value not in callers:
                        match = False; break
                elif field == "blueprint":
                    bp = str(node.metadata.get("blueprint", "")).lower()
                    if op == "=" and bp != value:
                        match = False; break
                elif field == "complexity":
                    cx = node.metadata.get("complexity")
                    if cx is None:
                        match = False; break
                    try:
                        val_f = float(value)
                        if op == ">" and not (float(cx) > val_f):
                            match = False; break
                        elif op == "<" and not (float(cx) < val_f):
                            match = False; break
                        elif op == "=" and float(cx) != val_f:
                            match = False; break
                    except ValueError:
                        match = False; break

            if match:
                results.append(node)

        results.sort(key=lambda n: n.label)
        return results[:limit]

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

    def top_risk(self, limit: int = 50) -> list[Node]:
        """Return the top-N highest-risk nodes sorted by risk_score descending.

        Only nodes with risk_score > 0 are included.  risk_score is set by
        GitChurnAnalyzer as ``int(complexity * churn_count)``.

        Args:
            limit: Maximum number of nodes to return (default 50).

        Returns:
            List of Node objects sorted by risk_score descending.
        """
        result = [
            n for n in self.nodes.values()
            if (n.metadata.get("risk_score") or 0) > 0
        ]
        result.sort(key=lambda n: -(n.metadata.get("risk_score") or 0))
        return result[:limit]

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

    def trace_route(self, route_id: str) -> dict:
        """Return the full execution chain for a route: route → actions → services → models.
        
        Returns a dict with keys:
          route: Node dict (the route itself)
          actions: list of Node dicts (called via `calls` edges from route)
          services: list of Node dicts (called via `calls` edges from actions, deduplicated)
          models: list of Node dicts (touched via `uses_model` from route/actions/services, deduplicated)
          edges: list of Edge dicts (all edges connecting nodes in the chain)
        
        Raises ValueError if route_id not found or node is not a route.
        """
        node = self.get_node(route_id)
        if not node:
            raise ValueError(f"Node '{route_id}' not found")
        if node.type != NodeType.ROUTE:
            raise ValueError(f"Node '{route_id}' is not a route (type: {node.type})")
        
        # actions: calls edges FROM route
        action_ids = {
            e.target for e in self.get_edges_from(route_id)
            if e.type == EdgeType.CALLS and
               self.get_node(e.target) and self.get_node(e.target).type == NodeType.ACTION
        }
        # services: calls edges FROM actions
        service_ids = set()
        for aid in action_ids:
            for e in self.get_edges_from(aid):
                if e.type == EdgeType.CALLS:
                    t = self.get_node(e.target)
                    if t and t.type == NodeType.SERVICE:
                        service_ids.add(e.target)
        # models: uses_model edges from route + actions + services
        model_ids = set()
        for src_id in {route_id} | action_ids | service_ids:
            for e in self.get_edges_from(src_id):
                if e.type == EdgeType.USES_MODEL:
                    t = self.get_node(e.target)
                    if t and t.type == NodeType.MODEL:
                        model_ids.add(e.target)
        
        # collect all edges between these nodes
        all_node_ids = {route_id} | action_ids | service_ids | model_ids
        chain_edges = [
            e for e in self.edges
            if e.source in all_node_ids and e.target in all_node_ids
        ]
        
        def _node(nid):
            n = self.get_node(nid)
            return n.to_dict() if n else None
        
        return {
            "route": node.to_dict(),
            "actions": [_node(i) for i in sorted(action_ids) if _node(i)],
            "services": [_node(i) for i in sorted(service_ids) if _node(i)],
            "models": [_node(i) for i in sorted(model_ids) if _node(i)],
            "edges": [e.to_dict() for e in chain_edges],
        }

    def blueprint_subgraph(self, blueprint_id: str) -> dict:
        """Return everything owned by a blueprint: routes, actions, services, models.
        
        Returns a dict with keys:
          blueprint: Node dict
          routes: list of Node dicts
          actions: list of Node dicts (reachable from routes via calls)
          services: list of Node dicts (reachable from actions via calls)
          models: list of Node dicts (reachable via uses_model from routes/actions/services)
          edges: list of all connecting Edge dicts
          stats: { route_count, action_count, service_count, model_count }
        
        Raises ValueError if blueprint_id not found or node is not a blueprint.
        """
        bp_node = self.get_node(blueprint_id)
        if not bp_node:
            raise ValueError(f"Node '{blueprint_id}' not found")
        if bp_node.type != NodeType.BLUEPRINT:
            raise ValueError(f"Node '{blueprint_id}' is not a blueprint")
        
        bp_label = bp_node.label
        
        # routes: route nodes where metadata.blueprint == bp_label
        route_nodes = [
            n for n in self.nodes.values()
            if n.type == NodeType.ROUTE and n.metadata.get("blueprint") == bp_label
        ]
        route_ids = {n.id for n in route_nodes}
        
        # actions from routes
        action_ids = set()
        for rid in route_ids:
            for e in self.get_edges_from(rid):
                if e.type == EdgeType.CALLS:
                    t = self.get_node(e.target)
                    if t and t.type == NodeType.ACTION:
                        action_ids.add(e.target)
        
        # services from actions
        service_ids = set()
        for aid in action_ids:
            for e in self.get_edges_from(aid):
                if e.type == EdgeType.CALLS:
                    t = self.get_node(e.target)
                    if t and t.type == NodeType.SERVICE:
                        service_ids.add(e.target)
        
        # models from routes + actions + services
        model_ids = set()
        for src_id in route_ids | action_ids | service_ids:
            for e in self.get_edges_from(src_id):
                if e.type == EdgeType.USES_MODEL:
                    t = self.get_node(e.target)
                    if t and t.type == NodeType.MODEL:
                        model_ids.add(e.target)
        
        all_node_ids = {blueprint_id} | route_ids | action_ids | service_ids | model_ids
        chain_edges = [
            e for e in self.edges
            if e.source in all_node_ids and e.target in all_node_ids
        ]
        
        def _nodes(ids):
            return sorted(
                [self.get_node(i).to_dict() for i in ids if self.get_node(i)],
                key=lambda n: n["label"]
            )
        
        return {
            "blueprint": bp_node.to_dict(),
            "routes": _nodes(route_ids),
            "actions": _nodes(action_ids),
            "services": _nodes(service_ids),
            "models": _nodes(model_ids),
            "edges": [e.to_dict() for e in chain_edges],
            "stats": {
                "route_count": len(route_ids),
                "action_count": len(action_ids),
                "service_count": len(service_ids),
                "model_count": len(model_ids),
            }
        }

    def locate(self, hint: str) -> dict:
        """Find the best-fit blueprint and service for a given feature hint.
        
        Scores blueprints and services by how many of their associated node labels/file_paths
        contain the hint terms (space-separated, case-insensitive).
        
        Returns:
          {
            "hint": str,
            "best_blueprint": Node dict or null,
            "best_service": Node dict or null,
            "candidate_blueprints": [{"node": Node dict, "score": int, "route_count": int}, ...] top 5,
            "candidate_services": [{"node": Node dict, "score": int}, ...] top 5,
          }
        """
        terms = [t.lower() for t in hint.strip().split() if t]
        if not terms:
            return {"hint": hint, "best_blueprint": None, "best_service": None,
                    "candidate_blueprints": [], "candidate_services": []}
        
        def score_text(text: str) -> int:
            t = text.lower()
            return sum(1 for term in terms if term in t)
        
        # score blueprints: own label + all routes they own
        blueprint_scores = []
        for node in self.nodes.values():
            if node.type != NodeType.BLUEPRINT:
                continue
            s = score_text(node.label) + score_text(node.file_path)
            route_count = 0
            for rn in self.nodes.values():
                if rn.type == NodeType.ROUTE and rn.metadata.get("blueprint") == node.label:
                    s += score_text(rn.label) + score_text(rn.file_path)
                    route_count += 1
            blueprint_scores.append({"node": node.to_dict(), "score": s, "route_count": route_count})
        
        blueprint_scores.sort(key=lambda x: -x["score"])
        top_blueprints = [b for b in blueprint_scores[:5] if b["score"] > 0]
        
        # score services
        service_scores = []
        for node in self.nodes.values():
            if node.type != NodeType.SERVICE:
                continue
            s = score_text(node.label) + score_text(node.file_path)
            service_scores.append({"node": node.to_dict(), "score": s})
        
        service_scores.sort(key=lambda x: -x["score"])
        top_services = [s for s in service_scores[:5] if s["score"] > 0]
        
        return {
            "hint": hint,
            "best_blueprint": top_blueprints[0]["node"] if top_blueprints else None,
            "best_service": top_services[0]["node"] if top_services else None,
            "candidate_blueprints": top_blueprints,
            "candidate_services": top_services,
        }

    def trace_node(self, node_id: str) -> dict:
        """Trace any node forward (what it calls) and backward (what calls it).

        Works for any node type — most useful for action, service, model, task.
        For routes, prefer trace_route() which structures the chain by layer.

        Returns:
          {
            node: Node dict,
            callers:  list of Node dicts that have an outgoing edge TO this node,
            callees:  list of Node dicts this node calls/uses (outgoing edges),
            models_used: list of model Node dicts (uses_model edges from this node),
            tasks_dispatched: list of task Node dicts (dispatches_task edges),
            edges: list of all connecting Edge dicts,
            summary: { caller_count, callee_count, model_count, task_count }
          }

        Raises ValueError if node_id not found.
        """
        node = self.get_node(node_id)
        if not node:
            raise ValueError(f"Node '{node_id}' not found")

        # Outgoing edges from this node
        out_edges = self.get_edges_from(node_id)
        callee_ids = {e.target for e in out_edges if e.type == EdgeType.CALLS}
        model_ids  = {e.target for e in out_edges if e.type == EdgeType.USES_MODEL}
        task_ids   = {e.target for e in out_edges if e.type == EdgeType.DISPATCHES_TASK}

        # Incoming edges to this node
        in_edges = self.get_edges_to(node_id)
        caller_ids = {e.source for e in in_edges}

        all_node_ids = {node_id} | callee_ids | model_ids | task_ids | caller_ids
        relevant_edges = [
            e for e in self.edges
            if e.source in all_node_ids and e.target in all_node_ids
        ]

        def _nodes(ids):
            return sorted(
                [self.get_node(i).to_dict() for i in ids if self.get_node(i)],
                key=lambda n: n["label"],
            )

        return {
            "node": node.to_dict(),
            "callers": _nodes(caller_ids),
            "callees": _nodes(callee_ids),
            "models_used": _nodes(model_ids),
            "tasks_dispatched": _nodes(task_ids),
            "edges": [e.to_dict() for e in relevant_edges],
            "summary": {
                "caller_count": len(caller_ids),
                "callee_count": len(callee_ids),
                "model_count": len(model_ids),
                "task_count": len(task_ids),
            },
        }

    def neighbors(self, node_id: str, depth: int = 2) -> dict:
        """Return the neighborhood subgraph around a node up to `depth` hops.

        Walks BOTH directions (forward + backward) so the result shows
        everything connected to the node within `depth` hops regardless of
        edge direction.  Useful for ad-hoc structural questions like
        "show me everything around model::User within 2 hops".

        Args:
            node_id: The focal node ID.
            depth:   Number of hops in each direction (default 2, max 5).

        Returns:
          {
            focal_node: Node dict,
            nodes: list of all Node dicts in the neighborhood (including focal),
            edges: list of all Edge dicts connecting those nodes,
            stats: { node_count, edge_count, by_type: {type: count} }
          }

        Raises ValueError if node_id not found.
        """
        if node_id not in self.nodes:
            raise ValueError(f"Node '{node_id}' not found")

        depth = min(depth, 5)

        visited: set[str] = set()
        queue: list[tuple[str, int]] = [(node_id, 0)]

        while queue:
            current_id, d = queue.pop(0)
            if current_id in visited or d > depth:
                continue
            visited.add(current_id)
            if d >= depth:
                continue
            # Walk both outgoing and incoming edges
            for edge in self.get_edges_from(current_id):
                if edge.target not in visited:
                    queue.append((edge.target, d + 1))
            for edge in self.get_edges_to(current_id):
                if edge.source not in visited:
                    queue.append((edge.source, d + 1))

        neighbor_nodes = [
            self.nodes[nid].to_dict() for nid in visited if nid in self.nodes
        ]
        neighbor_edges = [
            e.to_dict() for e in self.edges
            if e.source in visited and e.target in visited
        ]

        by_type: dict[str, int] = {}
        for n in neighbor_nodes:
            by_type[n["type"]] = by_type.get(n["type"], 0) + 1

        return {
            "focal_node": self.nodes[node_id].to_dict(),
            "nodes": neighbor_nodes,
            "edges": neighbor_edges,
            "stats": {
                "node_count": len(neighbor_nodes),
                "edge_count": len(neighbor_edges),
                "by_type": by_type,
            },
        }

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
        from flask_brain.scanners.property_scanner import PropertyScanner
        
        # Run all scanners that create nodes and edges
        scanners = [
            RouteScanner(project_path),
            ModelScanner(project_path),
            ServiceScanner(project_path),
            ViewFunctionTracer(project_path),
            CeleryTaskScanner(project_path),
            PropertyScanner(project_path),
        ]
        
        for scanner in scanners:
            nodes, edges = scanner.scan()
            self.add_scanner_output(nodes, edges)
        
        # Enrich nodes with complexity and query metadata
        complexity_analyzer = ComplexityAnalyzer(project_path)
        complexity_analyzer.enrich(self.graph)
        
        query_tracer = QueryTracer(project_path)
        query_tracer.enrich(self.graph)

        from flask_brain.scanners.git_churn_analyzer import GitChurnAnalyzer
        git_churn = GitChurnAnalyzer(project_path)
        git_churn.enrich(self.graph)

        return self.graph

    def get_graph(self) -> Graph:
        """Get the current graph."""
        return self.graph
