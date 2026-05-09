import type { Graph, Node, Edge } from '../types/graph';

// Edge types that are meaningful in a sequence diagram.
// Deliberately excludes 'has_relationship' (model↔model ORM links — too noisy).
const SEQUENCE_EDGE_TYPES = new Set(['calls', 'uses_model', 'dispatches_task']);

// Sanitise a label for use as a Mermaid participant alias (no spaces, colons, etc.)
function toAlias(label: string): string {
  return label.replace(/[^a-zA-Z0-9_]/g, '_').replace(/^_+|_+$/g, '');
}

// Human-readable display name for a node in the diagram
function displayName(node: Node): string {
  switch (node.type) {
    case 'route':
      return node.label;          // e.g. "GET /dashboard"
    case 'action':
      return node.label;          // view function name
    case 'service':
      return node.label;
    case 'model':
      return node.label;
    case 'task':
      return node.label;
    default:
      return node.label;
  }
}

interface Step {
  fromAlias: string;
  toAlias: string;
  label: string;
  isAsync: boolean;  // dispatches_task → async arrow
}

export function generateSequenceDiagram(graph: Graph, routeNode: Node): string {
  const nodeMap = new Map<string, Node>(graph.nodes.map(n => [n.id, n]));

  // BFS from the route node, following only meaningful edge types.
  // Stop at depth 3 to avoid explosion.
  const steps: Step[] = [];
  const visited = new Set<string>();
  const participantOrder: string[] = [];  // insertion-order for declaration

  const routeAlias = toAlias(routeNode.label);

  function ensureParticipant(alias: string) {
    if (!participantOrder.includes(alias)) {
      participantOrder.push(alias);
    }
  }

  // Seed
  ensureParticipant('Client');
  ensureParticipant(routeAlias);

  function traverse(nodeId: string, depth: number) {
    if (depth > 3 || visited.has(nodeId)) return;
    visited.add(nodeId);

    const outgoing = graph.edges.filter(
      e => e.source === nodeId && SEQUENCE_EDGE_TYPES.has(e.type)
    );

    for (const edge of outgoing) {
      const target = nodeMap.get(edge.target);
      if (!target) continue;

      const fromNode = nodeMap.get(nodeId)!;
      const fromAlias = toAlias(displayName(fromNode));
      const toAlias_ = toAlias(displayName(target));

      ensureParticipant(fromAlias);
      ensureParticipant(toAlias_);

      const label = edgeLabel(edge, target);
      const isAsync = edge.type === 'dispatches_task';
      steps.push({ fromAlias, toAlias: toAlias_, label, isAsync });

      traverse(edge.target, depth + 1);
    }
  }

  traverse(routeNode.id, 0);

  // ── Build the Mermaid source ─────────────────────────────────────────────
  const lines: string[] = ['sequenceDiagram'];

  // 1. Participant declarations (must come before any arrows)
  for (const alias of participantOrder) {
    // Use participant alias as display name, replacing _ back to spaces for readability
    const display = alias.replace(/_/g, ' ');
    lines.push(`    participant ${alias} as ${display}`);
  }

  // 2. Initial request arrow
  const method = routeNode.metadata?.methods?.[0] ?? 'GET';
  lines.push(`    Client->>${routeAlias}: ${method} ${routeNode.label}`);

  // 3. Traversal arrows
  if (steps.length === 0) {
    // Nothing interesting downstream — at least show the action call if one exists
    const actionEdge = graph.edges.find(
      e => e.source === routeNode.id && e.type === 'calls'
    );
    if (actionEdge) {
      const actionNode = nodeMap.get(actionEdge.target);
      if (actionNode) {
        const actionAlias = toAlias(displayName(actionNode));
        lines.push(`    ${routeAlias}->>${actionAlias}: invoke`);
        lines.push(`    ${actionAlias}-->>${routeAlias}: result`);
      }
    }
  } else {
    for (const step of steps) {
      if (step.isAsync) {
        lines.push(`    ${step.fromAlias}-)${step.toAlias}: ${step.label}`);
      } else {
        lines.push(`    ${step.fromAlias}->>${step.toAlias}: ${step.label}`);
        lines.push(`    ${step.toAlias}-->>${step.fromAlias}: result`);
      }
    }
  }

  // 4. Final response back to client
  lines.push(`    ${routeAlias}-->>Client: response`);

  return lines.join('\n');
}

function edgeLabel(edge: Edge, target: Node): string {
  switch (edge.type) {
    case 'calls':
      return `call ${target.label}`;
    case 'uses_model':
      return `query ${target.label}`;
    case 'dispatches_task':
      return `dispatch ${target.label}`;
    default:
      return edge.type;
  }
}
