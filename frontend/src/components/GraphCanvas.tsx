import { useEffect, useRef, useState } from 'react';
import cytoscape, { Core } from 'cytoscape';
import dagre from 'cytoscape-dagre';
import coseBilkent from 'cytoscape-cose-bilkent';
import { cytoscapeStyles } from '../utils/cytoscapeStyles';
import type { Graph, Node } from '../types/graph';

// Register layouts
cytoscape.use(dagre);
cytoscape.use(coseBilkent);

interface GraphCanvasProps {
  graph: Graph;
  onNodeSelect: (node: Node | null) => void;
  selectedNodeId: string | null;
}

type LayoutType = 'dagre' | 'cose-bilkent' | 'breadthfirst' | 'circle';

export function GraphCanvas({ graph, onNodeSelect, selectedNodeId }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [layout, setLayout] = useState<LayoutType>('dagre');

  useEffect(() => {
    if (!containerRef.current || !graph) return;

    // Initialize Cytoscape
    const cy = cytoscape({
      container: containerRef.current,
      elements: {
        nodes: graph.nodes.map(node => ({
          data: {
            ...node,
          },
        })),
        edges: graph.edges.map(edge => ({
          data: {
            id: `${edge.source}-${edge.target}`,
            source: edge.source,
            target: edge.target,
            type: edge.type,
          },
        })),
      },
      style: cytoscapeStyles,
      minZoom: 0.1,
      maxZoom: 3,
      wheelSensitivity: 0.2,
    });

    cyRef.current = cy;

    // Apply initial layout
    applyLayout(cy, layout);

    // Handle node selection
    cy.on('tap', 'node', (event) => {
      const node = event.target.data() as Node;
      onNodeSelect(node);
    });

    // Handle background tap (deselect)
    cy.on('tap', (event) => {
      if (event.target === cy) {
        onNodeSelect(null);
      }
    });

    // Handle node hover
    cy.on('mouseover', 'node', (event) => {
      const node = event.target.data() as Node;
      event.target.style('cursor', 'pointer');
      
      // Show tooltip
      const tooltip = document.createElement('div');
      tooltip.id = 'cy-tooltip';
      tooltip.className = 'absolute bg-gray-900 text-white px-3 py-2 rounded-lg text-sm shadow-lg z-50 pointer-events-none';
      tooltip.innerHTML = `
        <div class="font-semibold">${node.label}</div>
        <div class="text-gray-300 text-xs mt-1">${node.file_path}:${node.line_number}</div>
      `;
      document.body.appendChild(tooltip);
      
      const updateTooltipPosition = (e: MouseEvent) => {
        tooltip.style.left = `${e.clientX + 10}px`;
        tooltip.style.top = `${e.clientY + 10}px`;
      };
      
      document.addEventListener('mousemove', updateTooltipPosition);
      
      event.target.on('mouseout', () => {
        document.removeEventListener('mousemove', updateTooltipPosition);
        tooltip.remove();
      });
    });

    return () => {
      cy.destroy();
    };
  }, [graph, onNodeSelect]);

  // Update selected node styling
  useEffect(() => {
    if (!cyRef.current) return;
    
    cyRef.current.nodes().removeClass('selected');
    if (selectedNodeId) {
      cyRef.current.getElementById(selectedNodeId).addClass('selected');
    }
  }, [selectedNodeId]);

  // Update layout when changed
  useEffect(() => {
    if (!cyRef.current) return;
    applyLayout(cyRef.current, layout);
  }, [layout]);

  const applyLayout = (cy: Core, layoutType: LayoutType) => {
    let layoutOptions: any;

    switch (layoutType) {
      case 'dagre':
        layoutOptions = {
          name: 'dagre',
          rankDir: 'TB',
          nodeSep: 100,
          rankSep: 150,
          padding: 50,
        };
        break;
      case 'cose-bilkent':
        layoutOptions = {
          name: 'cose-bilkent',
          idealEdgeLength: 150,
          nodeRepulsion: 8000,
          padding: 50,
          randomize: false,
        };
        break;
      case 'breadthfirst':
        layoutOptions = {
          name: 'breadthfirst',
          directed: true,
          spacingFactor: 1.5,
          padding: 50,
        };
        break;
      case 'circle':
        layoutOptions = {
          name: 'circle',
          padding: 50,
        };
        break;
    }

    cy.layout(layoutOptions).run();
  };

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
    a.download = 'flask-brain-graph.png';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="relative w-full h-full">
      {/* Toolbar */}
      <div className="absolute top-4 left-4 z-10 bg-white dark:bg-gray-800 rounded-lg shadow-lg p-2 flex items-center gap-2">
        <select
          value={layout}
          onChange={(e) => setLayout(e.target.value as LayoutType)}
          className="px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="dagre">Hierarchical</option>
          <option value="cose-bilkent">Force-Directed</option>
          <option value="breadthfirst">Breadth-First</option>
          <option value="circle">Circle</option>
        </select>

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
