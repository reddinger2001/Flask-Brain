import { useState, useEffect, useRef } from 'react';
import cytoscape, { Core } from 'cytoscape';
import dagre from 'cytoscape-dagre';
import { cytoscapeStyles } from '../utils/cytoscapeStyles';
import type { Graph, Node, Manifest } from '../types/graph';

// Register dagre layout
cytoscape.use(dagre);

// Rank mapping for hierarchical layout
const RANK_MAP: Record<string, number> = {
  blueprint: 0,
  route: 1,
  action: 2,
  service: 2,
  task: 2,
  model: 3,
};

interface BlueprintExplorerProps {
  graph: Graph;
  onNodeSelect: (node: Node | null) => void;
  selectedNodeId: string | null;
  manifest?: Manifest | null;
}

interface BlueprintCard {
  id: string;
  label: string;
  routeCount: number;
  modelCount: number;
  topMethods: string[];
}

const METHOD_COLORS: Record<string, string> = {
  GET: 'bg-blue-600',
  POST: 'bg-green-600',
  PUT: 'bg-yellow-600',
  DELETE: 'bg-red-600',
  PATCH: 'bg-orange-600',
};

export function BlueprintExplorer({ graph, onNodeSelect, selectedNodeId }: BlueprintExplorerProps) {
  const [selectedBlueprintId, setSelectedBlueprintId] = useState<string | null>(null);
  const [blueprintCards, setBlueprintCards] = useState<BlueprintCard[]>([]);
  const cyRef = useRef<Core | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Build blueprint cards on mount
  useEffect(() => {
    const blueprints = graph.nodes.filter(n => n.type === 'blueprint');
    const cards: BlueprintCard[] = blueprints.map(bp => {
      // Find routes registered by this blueprint
      const routeEdges = graph.edges.filter(e => e.source === bp.id && e.type === 'registers_blueprint');
      const routeIds = routeEdges.map(e => e.target);
      const routes = graph.nodes.filter(n => routeIds.includes(n.id));

      // Find models touched by this blueprint
      const modelIds = new Set<string>();
      routeIds.forEach(routeId => {
        // route → calls → action
        const callsEdges = graph.edges.filter(e => e.source === routeId && e.type === 'calls');
        callsEdges.forEach(callsEdge => {
          const actionId = callsEdge.target;
          // action → uses_model → model
          const usesModelEdges = graph.edges.filter(e => e.source === actionId && e.type === 'uses_model');
          usesModelEdges.forEach(usesModelEdge => {
            modelIds.add(usesModelEdge.target);
          });
        });
      });

      // Collect HTTP methods
      const methodCounts: Record<string, number> = {};
      routes.forEach(route => {
        const methods = route.metadata.methods || [];
        methods.forEach(method => {
          methodCounts[method] = (methodCounts[method] || 0) + 1;
        });
      });

      // Top 3 methods by count
      const topMethods = Object.entries(methodCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3)
        .map(([method]) => method);

      return {
        id: bp.id,
        label: bp.label,
        routeCount: routes.length,
        modelCount: modelIds.size,
        topMethods,
      };
    });

    // Sort by route count descending
    cards.sort((a, b) => b.routeCount - a.routeCount);
    setBlueprintCards(cards);
  }, [graph]);

  // Render mini graph when a blueprint is selected
  useEffect(() => {
    if (!selectedBlueprintId || !containerRef.current) {
      if (cyRef.current) {
        cyRef.current.destroy();
        cyRef.current = null;
      }
      return;
    }

    // Build subgraph for this blueprint
    const blueprintNode = graph.nodes.find(n => n.id === selectedBlueprintId);
    if (!blueprintNode) return;

    const routeEdges = graph.edges.filter(e => e.source === selectedBlueprintId && e.type === 'registers_blueprint');
    const routeIds = routeEdges.map(e => e.target);
    const routeNodes = graph.nodes.filter(n => routeIds.includes(n.id));

    const actionIds = new Set<string>();
    const actionEdges: typeof graph.edges = [];
    routeIds.forEach(routeId => {
      const callsEdges = graph.edges.filter(e => e.source === routeId && e.type === 'calls');
      callsEdges.forEach(edge => {
        actionIds.add(edge.target);
        actionEdges.push(edge);
      });
    });
    const actionNodes = graph.nodes.filter(n => actionIds.has(n.id));

    const modelIds = new Set<string>();
    const modelEdges: typeof graph.edges = [];
    actionIds.forEach(actionId => {
      const usesModelEdges = graph.edges.filter(e => e.source === actionId && e.type === 'uses_model');
      usesModelEdges.forEach(edge => {
        modelIds.add(edge.target);
        modelEdges.push(edge);
      });
    });
    const modelNodes = graph.nodes.filter(n => modelIds.has(n.id));

    const allNodes = [blueprintNode, ...routeNodes, ...actionNodes, ...modelNodes];
    const allEdges = [...routeEdges, ...actionEdges, ...modelEdges];

    const cy = cytoscape({
      container: containerRef.current,
      elements: {
        nodes: allNodes.map(node => ({
          data: {
            ...node,
            rank: RANK_MAP[node.type] ?? 2,
          },
        })),
        edges: allEdges.map(edge => ({
          data: {
            id: `${edge.source}-${edge.target}`,
            source: edge.source,
            target: edge.target,
            type: edge.type,
          },
        })),
      },
      style: cytoscapeStyles,
      minZoom: 0.3,
      maxZoom: 2,
      wheelSensitivity: 0.2,
    });

    cyRef.current = cy;

    // Apply dagre layout
    cy.layout({
      name: 'dagre',
      rankDir: 'TB',
      align: 'UL',
      nodeSep: 40,
      rankSep: 80,
      padding: 40,
      animate: true,
      animationDuration: 300,
      fit: true,
    } as any).run();

    // Handle node clicks
    cy.on('tap', 'node', (event) => {
      const node = event.target.data() as Node;
      onNodeSelect(node);
    });

    // Handle background tap
    cy.on('tap', (event) => {
      if (event.target === cy) {
        onNodeSelect(null);
      }
    });

    return () => {
      cy.destroy();
    };
  }, [selectedBlueprintId, graph, onNodeSelect]);

  // Update selected node styling in mini graph
  useEffect(() => {
    if (!cyRef.current) return;
    
    cyRef.current.nodes().removeClass('selected');
    if (selectedNodeId) {
      cyRef.current.getElementById(selectedNodeId).addClass('selected');
    }
  }, [selectedNodeId]);

  // Level 1: Blueprint Cards Grid
  if (!selectedBlueprintId) {
    return (
      <div className="w-full h-full overflow-y-auto bg-gray-50 dark:bg-gray-900 p-8">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">Blueprint Explorer</h1>
          <p className="text-gray-600 dark:text-gray-400 mb-8">
            Click a blueprint to explore its routes, actions, and models
          </p>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {blueprintCards.map(card => (
              <div
                key={card.id}
                onClick={() => setSelectedBlueprintId(card.id)}
                className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm hover:shadow-md transition-shadow cursor-pointer border-l-4 border-l-teal-500 p-6"
              >
                <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-3">
                  {card.label}
                </h2>
                
                <div className="space-y-2 mb-4">
                  <div className="text-sm text-gray-600 dark:text-gray-400">
                    <span className="font-semibold text-gray-900 dark:text-white">{card.routeCount}</span> routes
                  </div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">
                    touches <span className="font-semibold text-gray-900 dark:text-white">{card.modelCount}</span> models
                  </div>
                </div>

                {card.topMethods.length > 0 && (
                  <div className="flex gap-2 mb-4">
                    {card.topMethods.map(method => (
                      <span
                        key={method}
                        className={`px-2 py-0.5 rounded text-xs font-bold text-white ${METHOD_COLORS[method] || 'bg-gray-600'}`}
                      >
                        {method}
                      </span>
                    ))}
                  </div>
                )}

                <div className="text-sm text-teal-600 dark:text-teal-400 font-medium flex items-center">
                  → Explore
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Level 2: Blueprint Drill-In
  const blueprintNode = graph.nodes.find(n => n.id === selectedBlueprintId);
  if (!blueprintNode) return null;

  // Build route table data
  const routeEdges = graph.edges.filter(e => e.source === selectedBlueprintId && e.type === 'registers_blueprint');
  const routeIds = routeEdges.map(e => e.target);
  const routes = graph.nodes.filter(n => routeIds.includes(n.id));

  const routeTableData = routes.map(route => {
    // Find action
    const callsEdge = graph.edges.find(e => e.source === route.id && e.type === 'calls');
    const actionNode = callsEdge ? graph.nodes.find(n => n.id === callsEdge.target) : null;

    // Find models touched by this action
    const modelNames: string[] = [];
    if (actionNode) {
      const usesModelEdges = graph.edges.filter(e => e.source === actionNode.id && e.type === 'uses_model');
      usesModelEdges.forEach(edge => {
        const modelNode = graph.nodes.find(n => n.id === edge.target);
        if (modelNode) modelNames.push(modelNode.label);
      });
    }

    return {
      routeId: route.id,
      methods: route.metadata.methods || [],
      path: route.label,
      action: actionNode?.label || '—',
      models: modelNames,
    };
  });

  // Count unique models
  const uniqueModels = new Set<string>();
  routeTableData.forEach(row => row.models.forEach(m => uniqueModels.add(m)));

  return (
    <div className="w-full h-full flex flex-col bg-gray-50 dark:bg-gray-900">
      {/* Header bar */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4 flex items-center gap-4">
        <button
          onClick={() => setSelectedBlueprintId(null)}
          className="px-3 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg text-sm font-medium text-gray-900 dark:text-white transition-colors flex items-center gap-2"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back
        </button>
        
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{blueprintNode.label}</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            {routes.length} routes · {uniqueModels.size} models
          </p>
        </div>
      </div>

      {/* Content area: table + mini graph */}
      <div className="flex-1 overflow-hidden flex flex-col lg:flex-row">
        {/* Route table */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-50 dark:bg-gray-700 border-b border-gray-200 dark:border-gray-600">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wider">
                    Method
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wider">
                    Path
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wider">
                    Action
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wider">
                    Models Touched
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {routeTableData.map(row => (
                  <tr
                    key={row.routeId}
                    className="hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors cursor-pointer"
                    onClick={() => {
                      const node = graph.nodes.find(n => n.id === row.routeId);
                      if (node) onNodeSelect(node);
                    }}
                  >
                    <td className="px-4 py-3">
                      <div className="flex gap-1">
                        {row.methods.map(method => (
                          <span
                            key={method}
                            className={`px-2 py-0.5 rounded text-xs font-bold text-white ${METHOD_COLORS[method] || 'bg-gray-600'}`}
                          >
                            {method}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <code className="text-sm text-gray-900 dark:text-gray-100 font-mono">
                        {row.path}
                      </code>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100">
                      {row.action}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">
                      {row.models.length > 0 ? row.models.join(', ') : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Mini graph */}
        <div className="w-full lg:w-96 border-t lg:border-t-0 lg:border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wider mb-3">
            Dependency Graph
          </h2>
          <div
            ref={containerRef}
            className="w-full bg-gray-50 dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700"
            style={{ height: '500px' }}
          />
        </div>
      </div>
    </div>
  );
}
