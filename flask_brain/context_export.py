"""AI context export for Flask Brain — Phase 6.

Performs a BFS from a focal node (up to `depth` hops), collects all reachable
nodes and the edges between them, then renders a deterministic Markdown
document suitable for pasting into an AI chat window.

Token budget is enforced by estimating `words × 1.3 ≈ tokens`; the source
snippet section is appended last so it is the first thing truncated.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask_brain.graph import Graph, Node


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def export_context(graph: "Graph", node_id: str, budget: int = 4000, depth: int = 3) -> str:
    """Return an AI-ready Markdown context block for *node_id*.

    Parameters
    ----------
    graph:
        The full project graph (loaded from ``graph-all.json``).
    node_id:
        ID of the focal node (e.g. ``"route::GET /dashboard"``).
    budget:
        Approximate token budget.  Token count is estimated as ``words × 1.3``.
        The source-snippet section is the last to be added and first to be
        dropped if the budget is exceeded.
    depth:
        BFS depth limit (default 3).
    """
    # Locate focal node
    # graph.nodes is a dict {id: Node}
    node_map: dict[str, "Node"] = dict(graph.nodes)
    focal = node_map.get(node_id)
    if focal is None:
        raise ValueError(f"Node not found: {node_id!r}")

    # BFS — collect reachable nodes within `depth` hops (both directions)
    visited: dict[str, int] = {node_id: 0}  # id → depth reached
    queue: deque[tuple[str, int]] = deque([(node_id, 0)])

    # Build adjacency index for fast lookup
    outgoing: dict[str, list] = {}  # source → [edges]
    incoming: dict[str, list] = {}  # target → [edges]
    for e in graph.edges:
        outgoing.setdefault(e.source, []).append(e)
        incoming.setdefault(e.target, []).append(e)

    while queue:
        current_id, current_depth = queue.popleft()
        if current_depth >= depth:
            continue
        for e in outgoing.get(current_id, []):
            if e.target not in visited:
                visited[e.target] = current_depth + 1
                queue.append((e.target, current_depth + 1))
        for e in incoming.get(current_id, []):
            if e.source not in visited:
                visited[e.source] = current_depth + 1
                queue.append((e.source, current_depth + 1))

    # Collect subgraph nodes in BFS order (deterministic — sort by depth then id)
    subgraph_nodes = sorted(
        [node_map[nid] for nid in visited if nid in node_map],
        key=lambda n: (visited[n.id], n.id),
    )

    # Collect subgraph edges (both endpoints must be in visited set)
    subgraph_edges = sorted(
        [e for e in graph.edges if e.source in visited and e.target in visited],
        key=lambda e: (e.source, e.target),
    )

    # -----------------------------------------------------------------------
    # Render sections
    # -----------------------------------------------------------------------
    sections: list[str] = []

    # 1. Header
    sections.append(_header(focal))

    # 2. Call chain (outgoing edges from focal)
    call_chain = _call_chain(focal, outgoing, node_map, depth)
    if call_chain:
        sections.append(call_chain)

    # 3. Complexity table
    complexity = _complexity_table(subgraph_nodes)
    if complexity:
        sections.append(complexity)

    # 4. DB operations
    db_ops = _db_operations(subgraph_nodes)
    if db_ops:
        sections.append(db_ops)

    # 5. Full node list
    sections.append(_node_list(subgraph_nodes, visited))

    # 6. Edge list
    if subgraph_edges:
        sections.append(_edge_list(subgraph_edges))

    # Build body without source snippets first
    body = "\n\n".join(sections)

    # 7. Source snippets — appended last, truncated if over budget
    source_section = _source_snippets(subgraph_nodes, budget, body)
    if source_section:
        candidate = body + "\n\n" + source_section
        if _estimate_tokens(candidate) <= budget:
            body = candidate

    # Final hard truncation if still over budget
    body = _truncate_to_budget(body, budget)

    return body


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def _header(node: "Node") -> str:
    lines = [
        "# Flask Brain — AI Context Export",
        "",
        "## Focal Node",
        f"- **ID:** `{node.id}`",
        f"- **Type:** {node.type}",
        f"- **Label:** {node.label}",
        f"- **File:** `{node.file_path}` line {node.line_number}",
    ]
    meta = node.metadata
    if meta:
        lines.append("")
        lines.append("### Metadata")
        for k, v in sorted(meta.items()):
            lines.append(f"- **{k}:** {v}")
    return "\n".join(lines)


def _call_chain(
    focal: "Node",
    outgoing: dict[str, list],
    node_map: dict[str, "Node"],
    depth: int,
) -> str:
    """DFS call chain from focal node."""
    lines: list[str] = ["## Call Chain"]
    seen: set[str] = set()

    def _walk(node_id: str, current_depth: int, prefix: str = ""):
        if current_depth > depth or node_id in seen:
            return
        seen.add(node_id)
        node = node_map.get(node_id)
        if node is None:
            return
        indent = "  " * current_depth
        tag = f"[{node.type}]" if node_id != focal.id else "[focal]"
        lines.append(f"{indent}- `{node.label}` {tag} `{node.file_path}:{node.line_number}`")
        for e in sorted(outgoing.get(node_id, []), key=lambda e: e.target):
            _walk(e.target, current_depth + 1)

    _walk(focal.id, 0)

    if len(lines) <= 1:
        return ""
    return "\n".join(lines)


def _complexity_table(nodes: list["Node"]) -> str:
    rows = [
        (n.label, n.type, n.metadata.get("complexity", "—"))
        for n in nodes
        if "complexity" in n.metadata
    ]
    if not rows:
        return ""
    lines = [
        "## Complexity",
        "",
        "| Node | Type | Complexity |",
        "|------|------|------------|",
    ]
    for label, ntype, c in sorted(rows, key=lambda r: str(r[2]) if r[2] != "—" else "0", reverse=True):
        lines.append(f"| {label} | {ntype} | {c} |")
    return "\n".join(lines)


def _db_operations(nodes: list["Node"]) -> str:
    rows = []
    for n in nodes:
        ops = n.metadata.get("db_operations")
        if ops:
            rows.append((n.label, ops))
    if not rows:
        return ""
    lines = ["## DB Operations"]
    for label, ops in sorted(rows, key=lambda r: r[0]):
        ops_str = ", ".join(ops) if isinstance(ops, list) else str(ops)
        lines.append(f"- **{label}:** {ops_str}")
    return "\n".join(lines)


def _node_list(nodes: list["Node"], visited: dict[str, int]) -> str:
    lines = ["## Nodes in Subgraph"]
    for n in nodes:
        hop = visited.get(n.id, "?")
        lines.append(f"- `{n.id}` ({n.type}, depth {hop}) — `{n.file_path}:{n.line_number}`")
    return "\n".join(lines)


def _edge_list(edges: list) -> str:
    lines = ["## Edges"]
    for e in edges:
        lines.append(f"- `{e.source}` → `{e.target}` [{e.type}]")
    return "\n".join(lines)


def _source_snippets(nodes: list["Node"], budget: int, existing_body: str) -> str:
    """Read up to 30 lines around each node's definition, budget permitting."""
    lines = ["## Source Snippets"]
    for n in nodes:
        path = Path(n.file_path)
        if not path.exists():
            continue
        try:
            all_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            start = max(0, n.line_number - 1)
            end = min(len(all_lines), n.line_number + 29)
            snippet = "\n".join(all_lines[start:end])
            lines.append(f"\n### `{n.label}` ({n.file_path}:{n.line_number})")
            lines.append(f"```python\n{snippet}\n```")
        except OSError:
            continue

    if len(lines) <= 1:
        return ""
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Token budget helpers
# ---------------------------------------------------------------------------

def _estimate_tokens(text: str) -> float:
    return len(text.split()) * 1.3


def _truncate_to_budget(text: str, budget: int) -> str:
    if _estimate_tokens(text) <= budget:
        return text
    # Hard-truncate by words
    words = text.split()
    max_words = int(budget / 1.3)
    return " ".join(words[:max_words]) + "\n\n*(truncated to fit token budget)*"
