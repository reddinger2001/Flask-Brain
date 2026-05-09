import { BlueprintExplorer } from './BlueprintExplorer';
import type { Graph, Node, Manifest } from '../types/graph';

interface GraphCanvasProps {
  graph: Graph;
  onNodeSelect: (node: Node | null) => void;
  selectedNodeId: string | null;
  navigateTo?: Node | null;
  manifest?: Manifest | null;
}

export function GraphCanvas({ graph, onNodeSelect, selectedNodeId, manifest }: GraphCanvasProps) {
  return (
    <BlueprintExplorer
      graph={graph}
      onNodeSelect={onNodeSelect}
      selectedNodeId={selectedNodeId}
      manifest={manifest}
    />
  );
}
