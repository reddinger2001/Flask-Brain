import type { Graph, Node, Edge } from '../types/graph';

export function generateSequenceDiagram(graph: Graph, routeNode: Node): string {
  // Build a sequence diagram from the route node
  const lines: string[] = ['sequenceDiagram'];
  
  // Find all nodes connected to this route
  const visited = new Set<string>();
  const sequence: Array<{ from: string; to: string; label: string }> = [];
  
  function traverse(nodeId: string, depth: number = 0) {
    if (depth > 5 || visited.has(nodeId)) return;
    visited.add(nodeId);
    
    const outgoingEdges = graph.edges.filter(e => e.source === nodeId);
    
    for (const edge of outgoingEdges) {
      const targetNode = graph.nodes.find(n => n.id === edge.target);
      if (!targetNode) continue;
      
      const sourceNode = graph.nodes.find(n => n.id === nodeId);
      if (!sourceNode) continue;
      
      const fromLabel = getParticipantLabel(sourceNode);
      const toLabel = getParticipantLabel(targetNode);
      const edgeLabel = getEdgeLabel(edge, targetNode);
      
      sequence.push({ from: fromLabel, to: toLabel, label: edgeLabel });
      
      traverse(edge.target, depth + 1);
    }
  }
  
  // Start from the route node
  lines.push('    participant Client');
  lines.push(`    participant ${getParticipantLabel(routeNode)}`);
  
  // Add initial request
  lines.push(`    Client->>+${getParticipantLabel(routeNode)}: ${routeNode.metadata.methods?.[0] || 'GET'} ${routeNode.label}`);
  
  // Traverse the graph
  traverse(routeNode.id);
  
  // Add participants
  const participants = new Set<string>();
  sequence.forEach(({ from, to }) => {
    participants.add(from);
    participants.add(to);
  });
  
  participants.forEach(p => {
    if (p !== 'Client' && p !== getParticipantLabel(routeNode)) {
      lines.push(`    participant ${p}`);
    }
  });
  
  // Add sequence calls
  sequence.forEach(({ from, to, label }) => {
    lines.push(`    ${from}->>+${to}: ${label}`);
    lines.push(`    ${to}-->>-${from}: return`);
  });
  
  // Add final response
  lines.push(`    ${getParticipantLabel(routeNode)}-->>-Client: response`);
  
  return lines.join('\n');
}

function getParticipantLabel(node: Node): string {
  switch (node.type) {
    case 'route':
      return 'Route';
    case 'action':
      return node.label;
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

function getEdgeLabel(edge: Edge, targetNode: Node): string {
  switch (edge.type) {
    case 'calls':
      return targetNode.label;
    case 'uses_model':
      return `query ${targetNode.label}`;
    case 'dispatches_task':
      return `dispatch ${targetNode.label}`;
    default:
      return edge.type;
  }
}
