import { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';
import { generateSequenceDiagram } from '../utils/mermaid';
import { useGraph } from '../hooks/useGraph';
import type { Node } from '../types/graph';

interface SequenceDiagramProps {
  routeNode: Node;
}

export function SequenceDiagram({ routeNode }: SequenceDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Use same safeId derivation as GraphCanvas to match file names written by graph.py
  const safeRouteId = routeNode.id.replace('::', '_').replace(/\//g, '_').replace(/ /g, '_');
  const { graph, loading } = useGraph(`/api/graph/${safeRouteId}`);

  useEffect(() => {
    if (!graph || !containerRef.current) return;

    try {
      // Initialize mermaid
      mermaid.initialize({
        startOnLoad: false,
        theme: document.documentElement.classList.contains('dark') ? 'dark' : 'default',
        securityLevel: 'loose',
      });

      // Generate diagram
      const diagramCode = generateSequenceDiagram(graph, routeNode);
      
      // Render
      const id = `mermaid-${Date.now()}`;
      containerRef.current.innerHTML = `<div class="mermaid" id="${id}">${diagramCode}</div>`;
      
      mermaid.run({
        nodes: [document.getElementById(id)!],
      });
      
      setError(null);
    } catch (err) {
      console.error('Error rendering sequence diagram:', err);
      setError('Failed to render sequence diagram');
    }
  }, [graph, routeNode]);

  const handleExport = async () => {
    if (!containerRef.current) return;
    
    const svg = containerRef.current.querySelector('svg');
    if (!svg) return;
    
    const svgData = new XMLSerializer().serializeToString(svg);
    const blob = new Blob([svgData], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = `sequence-${routeNode.label.replace(/[^a-zA-Z0-9]/g, '-')}.svg`;
    a.click();
    
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
        <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Sequence Diagram</h4>
        <button
          onClick={handleExport}
          className="px-2 py-1 text-xs bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded transition-colors"
          title="Export as SVG"
        >
          Export
        </button>
      </div>
      <div
        ref={containerRef}
        className="bg-white dark:bg-gray-900 rounded-lg p-4 overflow-x-auto"
      />
    </div>
  );
}
