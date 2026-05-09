import { useEffect, useRef } from 'react';
import cytoscape, { Core } from 'cytoscape';
import coseBilkent from 'cytoscape-cose-bilkent';
import { NODE_COLORS } from '../utils/cytoscapeStyles';
import type { Graph, Node } from '../types/graph';

cytoscape.use(coseBilkent);

interface ERDViewProps {
  graph: Graph;
  onNodeSelect: (node: Node | null) => void;
}

export function ERDView({ graph, onNodeSelect }: ERDViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Filter to only model nodes and relationship edges
    const modelNodes = graph.nodes.filter(n => n.type === 'model');
    const relationshipEdges = graph.edges.filter(e => e.type === 'has_relationship');

    if (modelNodes.length === 0) {
      return;
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements: {
        nodes: modelNodes.map(node => ({
          data: {
            ...node,
          },
        })),
        edges: relationshipEdges.map(edge => ({
          data: {
            id: `${edge.source}-${edge.target}`,
            source: edge.source,
            target: edge.target,
            type: edge.type,
            label: edge.metadata.relationship_name || '',
          },
        })),
      },
      style: [
        {
          selector: 'node',
          style: {
            'background-color': NODE_COLORS.model,
            'label': 'data(label)',
            'color': '#fff',
            'text-valign': 'center',
            'text-halign': 'center',
            'font-size': '14px',
            'font-weight': 'bold',
            'width': '120px',
            'height': '120px',
            'text-wrap': 'wrap',
            'text-max-width': '110px',
            'border-width': 3,
            'border-color': '#fff',
            'shape': 'round-rectangle',
          },
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 5,
            'border-color': '#FFD700',
          },
        },
        {
          selector: 'edge',
          style: {
            'width': 3,
            'line-color': NODE_COLORS.model,
            'target-arrow-color': NODE_COLORS.model,
            'target-arrow-shape': 'triangle',
            'source-arrow-color': NODE_COLORS.model,
            'source-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'arrow-scale': 2,
            'label': 'data(label)',
            'font-size': '10px',
            'text-rotation': 'autorotate',
            'text-margin-y': -10,
          },
        },
      ],
      minZoom: 0.1,
      maxZoom: 3,
    });

    cyRef.current = cy;

    // Apply layout
    cy.layout({
      name: 'cose-bilkent',
      idealEdgeLength: 200,
      nodeRepulsion: 10000,
      padding: 50,
      randomize: false,
    } as any).run();

    // Handle node selection
    cy.on('tap', 'node', (event) => {
      const node = event.target.data() as Node;
      onNodeSelect(node);
    });

    cy.on('tap', (event) => {
      if (event.target === cy) {
        onNodeSelect(null);
      }
    });

    return () => {
      cy.destroy();
    };
  }, [graph, onNodeSelect]);

  const handleFit = () => {
    if (cyRef.current) {
      cyRef.current.fit(undefined, 50);
    }
  };

  const handleExportPNG = () => {
    if (!cyRef.current) return;
    
    const png = cyRef.current.png({
      output: 'blob',
      bg: 'white',
      full: true,
      scale: 2,
    });
    
    const url = URL.createObjectURL(png as Blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'flask-brain-erd.png';
    a.click();
    URL.revokeObjectURL(url);
  };

  const modelCount = graph.nodes.filter(n => n.type === 'model').length;

  if (modelCount === 0) {
    return (
      <div className="h-full flex items-center justify-center bg-white dark:bg-gray-900">
        <div className="text-center">
          <svg className="mx-auto h-16 w-16 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
          </svg>
          <p className="mt-4 text-lg text-gray-600 dark:text-gray-400">No models found in the graph.</p>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-500">
            Models will appear here once they are detected in your Flask application.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full">
      {/* Toolbar */}
      <div className="absolute top-4 left-4 z-10 bg-white dark:bg-gray-800 rounded-lg shadow-lg p-2 flex items-center gap-2">
        <div className="px-3 py-2 text-sm font-semibold text-gray-900 dark:text-white">
          {modelCount} Model{modelCount !== 1 ? 's' : ''}
        </div>

        <button
          onClick={handleFit}
          className="px-3 py-2 bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 border border-gray-300 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white transition-colors"
          title="Fit to view"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
          </svg>
        </button>

        <button
          onClick={handleExportPNG}
          className="px-3 py-2 bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 border border-gray-300 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white transition-colors"
          title="Export as PNG"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
        </button>
      </div>

      {/* Canvas */}
      <div ref={containerRef} className="w-full h-full bg-gray-50 dark:bg-gray-900" />
    </div>
  );
}
