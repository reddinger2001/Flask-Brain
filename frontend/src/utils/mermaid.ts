import type { Graph, Node, Edge } from '../types/graph';

// Edge types meaningful in a sequence diagram (no model↔model ORM noise)
const SEQUENCE_EDGE_TYPES = new Set(['calls', 'uses_model', 'dispatches_task']);

/** Sanitise a string into a valid Mermaid participant alias (alphanumeric + underscore only) */
function toAlias(s: string): string {
  return s.replace(/[^a-zA-Z0-9]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '') || 'Node';
}

/** Quote an arrow label so Mermaid accepts slashes, angle brackets, colons etc. */
function quoteLabel(s: string): string {
  return `"${s.replace(/"/g, "'")}"`;
}

/**
 * Format a participant display name for `participant ALIAS as DISPLAY`.
 * Mermaid does NOT support quoted strings in the `as` clause — they render literally.
 * So we just return the raw string. If it contains chars Mermaid can't handle,
 * callers should fall back to alias-only (no `as` clause).
 */
function quoteDisplay(s: string): string {
  // Replace any problematic chars with spaces so Mermaid renders a readable label
  // without double-quote literals showing up in the diagram.
  return s.replace(/[<>:;"]/g, ' ').replace(/\s+/g, ' ').trim();
}

interface Step {
  fromAlias: string;
  toAlias: string;
  label: string;
  isAsync: boolean;
}

export function generateSequenceDiagram(graph: Graph, routeNode: Node): string {
  const nodeMap = new Map<string, Node>(graph.nodes.map(n => [n.id, n]));

  // Use the view function name as the handler participant — much shorter than the URL
  const handlerName = routeNode.metadata?.view_function ?? routeNode.label;
  const handlerAlias = toAlias(handlerName);

  const participantAliases = new Map<string, string>(); // nodeId → alias
  const participantOrder: Array<{ alias: string; display: string }> = [];

  function ensureParticipant(nodeId: string, alias: string, display: string) {
    if (!participantAliases.has(nodeId)) {
      participantAliases.set(nodeId, alias);
      if (!participantOrder.find(p => p.alias === alias)) {
        participantOrder.push({ alias, display });
      }
    }
    return alias;
  }

  // Seed: Client and the handler
  ensureParticipant('__client__', 'Client', 'Client');
  ensureParticipant(routeNode.id, handlerAlias, handlerName);

  const steps: Step[] = [];
  const visited = new Set<string>();

  function traverse(nodeId: string, depth: number) {
    if (depth > 3 || visited.has(nodeId)) return;
    visited.add(nodeId);

    const outgoing = graph.edges.filter(
      e => e.source === nodeId && SEQUENCE_EDGE_TYPES.has(e.type)
    );

    for (const edge of outgoing) {
      const target = nodeMap.get(edge.target);
      if (!target) continue;

      const fromAlias = participantAliases.get(nodeId) ?? toAlias(nodeId);
      const targetAlias = toAlias(target.label);

      // Skip the route→action edge when the action IS the view function (self-loop)
      // The route node already represents the handler — no need to show a self-call
      if (nodeId === routeNode.id && edge.type === 'calls' && target.label === handlerName) {
        // Still traverse deeper from the action node so its calls are included
        ensureParticipant(target.id, targetAlias, target.label);
        traverse(edge.target, depth + 1);
        continue;
      }

      ensureParticipant(target.id, targetAlias, target.label);

      steps.push({
        fromAlias,
        toAlias: targetAlias,
        label: edgeLabel(edge, target),
        isAsync: edge.type === 'dispatches_task',
      });

      traverse(edge.target, depth + 1);
    }
  }

  traverse(routeNode.id, 0);

  // ── Build Mermaid source ─────────────────────────────────────────────────
  const lines: string[] = ['sequenceDiagram'];

  // Participant declarations MUST come before any arrows
  for (const { alias, display } of participantOrder) {
    const displayName = quoteDisplay(display);
    // Only emit `as DISPLAY` when the display differs from the alias
    const asClause = displayName !== alias ? ` as ${displayName}` : '';
    lines.push(`    participant ${alias}${asClause}`);
  }

  // Initial request
  const method = routeNode.metadata?.methods?.[0] ?? 'GET';
  lines.push(`    Client->>${handlerAlias}: ${quoteLabel(`${method} ${routeNode.label}`)}`);

  // Downstream calls
  if (steps.length === 0) {
    // Route with no downstream edges — at minimum show it does something
    lines.push(`    ${handlerAlias}-->>Client: ${quoteLabel('response')}`);
  } else {
    for (const step of steps) {
      if (step.isAsync) {
        lines.push(`    ${step.fromAlias}-) ${step.toAlias}: ${quoteLabel(step.label)}`);
      } else {
        lines.push(`    ${step.fromAlias}->>${step.toAlias}: ${quoteLabel(step.label)}`);
        lines.push(`    ${step.toAlias}-->>${step.fromAlias}: ${quoteLabel('result')}`);
      }
    }
    lines.push(`    ${handlerAlias}-->>Client: ${quoteLabel('response')}`);
  }

  return lines.join('\n');
}

function edgeLabel(edge: Edge, target: Node): string {
  switch (edge.type) {
    case 'calls':      return `call ${target.label}`;
    case 'uses_model': return `query ${target.label}`;
    case 'dispatches_task': return `dispatch ${target.label}`;
    default:           return edge.type;
  }
}
