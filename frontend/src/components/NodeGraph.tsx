import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import cytoscape, { Core, NodeSingular } from 'cytoscape';
import dagre from 'cytoscape-dagre';
import { NODE_COLORS } from '../utils/cytoscapeStyles';
import type { Graph, Node } from '../types/graph';

cytoscape.use(dagre);

// ─── Types ────────────────────────────────────────────────────────────────────

interface NodeGraphProps {
  graph: Graph;
  onNodeSelect: (node: Node | null) => void;
  selectedNodeId: string | null;
  /** When set, immediately focuses this node (e.g. "Show in Graph" from sidebar) */
  focusNodeId?: string | null;
}

type NodeTypeKey = 'blueprint' | 'route' | 'action' | 'service' | 'model' | 'task';
type EdgeTypeKey = 'calls' | 'uses_model' | 'has_relationship' | 'registers_blueprint';

const NODE_TYPE_LABELS: Record<NodeTypeKey, string> = {
  blueprint: 'Blueprints',
  route: 'Routes',
  action: 'Actions',
  service: 'Services',
  model: 'Models',
  task: 'Tasks',
};

const EDGE_TYPE_LABELS: Record<EdgeTypeKey, string> = {
  calls: 'Calls',
  uses_model: 'Uses Model',
  has_relationship: 'Has Relationship',
  registers_blueprint: 'Registers Blueprint',
};

const EDGE_COLORS: Record<EdgeTypeKey, string> = {
  calls: '#2196F3',
  uses_model: '#9C27B0',
  has_relationship: '#F44336',
  registers_blueprint: '#009688',
};

const ALL_NODE_TYPES: NodeTypeKey[] = ['blueprint', 'route', 'action', 'service', 'model', 'task'];
const ALL_EDGE_TYPES: EdgeTypeKey[] = ['calls', 'uses_model', 'has_relationship', 'registers_blueprint'];

// ─── Neighbourhood computation ────────────────────────────────────────────────

function getNeighborhood(
  graph: Graph,
  focalId: string,
  depth: number,
  visibleNodeTypes: Set<string>,
  visibleEdgeTypes: Set<string>,
): { nodes: Graph['nodes']; edges: Graph['edges'] } {
  const visitedIds = new Set<string>([focalId]);
  let frontier = new Set<string>([focalId]);

  for (let d = 0; d < depth; d++) {
    const next = new Set<string>();
    for (const edge of graph.edges) {
      if (!visibleEdgeTypes.has(edge.type)) continue;
      if (frontier.has(edge.source) && !visitedIds.has(edge.target)) {
        next.add(edge.target);
      }
      if (frontier.has(edge.target) && !visitedIds.has(edge.source)) {
        next.add(edge.source);
      }
    }
    next.forEach(id => visitedIds.add(id));
    frontier = next;
    if (next.size === 0) break;
  }

  const nodeMap = new Map(graph.nodes.map(n => [n.id, n]));
  const visibleNodes = [...visitedIds]
    .map(id => nodeMap.get(id))
    .filter((n): n is Graph['nodes'][0] => !!n && visibleNodeTypes.has(n.type));

  const visibleNodeIds = new Set(visibleNodes.map(n => n.id));
  const visibleEdges = graph.edges.filter(
    e =>
      visibleEdgeTypes.has(e.type) &&
      visibleNodeIds.has(e.source) &&
      visibleNodeIds.has(e.target),
  );

  return { nodes: visibleNodes, edges: visibleEdges };
}

// ─── Component ───────────────────────────────────────────────────────────────

export function NodeGraph({ graph, onNodeSelect, selectedNodeId, focusNodeId }: NodeGraphProps) {
  const cyRef = useRef<Core | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Search
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Graph['nodes']>([]);
  const [showResults, setShowResults] = useState(false);

  // Focal node
  const [focalNodeId, setFocalNodeId] = useState<string | null>(null);
  const [focalNode, setFocalNode] = useState<Graph['nodes'][0] | null>(null);

  // Controls
  const [depth, setDepth] = useState(2);
  const [visibleNodeTypes, setVisibleNodeTypes] = useState<Set<NodeTypeKey>>(
    new Set(ALL_NODE_TYPES),
  );
  const [visibleEdgeTypes, setVisibleEdgeTypes] = useState<Set<EdgeTypeKey>>(
    new Set(ALL_EDGE_TYPES),
  );

  // Stats
  const [neighborhoodStats, setNeighborhoodStats] = useState({ nodes: 0, edges: 0 });

  // ── Respond to external focusNodeId (e.g. "Show in Graph" from Sidebar) ──
  useEffect(() => {
    if (focusNodeId) {
      const n = graph.nodes.find(node => node.id === focusNodeId);
      if (n) {
        setFocalNodeId(focusNodeId);
        setFocalNode(n);
        setSearchQuery(n.label);
        setShowResults(false);
      }
    }
  }, [focusNodeId, graph.nodes]);

  // ── Search ──────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!searchQuery.trim() || searchQuery === focalNode?.label) {
      setSearchResults([]);
      setShowResults(false);
      return;
    }
    const q = searchQuery.toLowerCase();
    const results = graph.nodes
      .filter(n => n.label.toLowerCase().includes(q) || n.id.toLowerCase().includes(q))
      .slice(0, 20);
    setSearchResults(results);
    setShowResults(results.length > 0);
  }, [searchQuery, graph.nodes, focalNode]);

  const selectFocal = useCallback(
    (node: Graph['nodes'][0]) => {
      setFocalNodeId(node.id);
      setFocalNode(node);
      setSearchQuery(node.label);
      setShowResults(false);
      onNodeSelect(node as Node);
    },
    [onNodeSelect],
  );

  // ── Build neighbourhood ──────────────────────────────────────────────────
  const neighborhood = useMemo(() => {
    if (!focalNodeId) return null;
    return getNeighborhood(graph, focalNodeId, depth, visibleNodeTypes, visibleEdgeTypes);
  }, [focalNodeId, graph, depth, visibleNodeTypes, visibleEdgeTypes]);

  // ── Render / update Cytoscape ────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;

    // Destroy old instance
    if (cyRef.current) {
      cyRef.current.destroy();
      cyRef.current = null;
    }

    if (!neighborhood) return;

    setNeighborhoodStats({ nodes: neighborhood.nodes.length, edges: neighborhood.edges.length });

    const elements = [
      ...neighborhood.nodes.map(n => ({
        data: {
          id: n.id,
          label: n.label,
          type: n.type,
          isFocal: n.id === focalNodeId,
        },
      })),
      ...neighborhood.edges.map(e => ({
        data: {
          id: `${e.source}-${e.type}-${e.target}`,
          source: e.source,
          target: e.target,
          type: e.type,
        },
      })),
    ];

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': (ele: NodeSingular) =>
              NODE_COLORS[ele.data('type') as NodeTypeKey] || '#999',
            label: 'data(label)',
            color: '#fff',
            'text-valign': 'center',
            'text-halign': 'center',
            'font-size': '11px',
            'font-weight': 'bold',
            width: 72,
            height: 72,
            'text-wrap': 'wrap',
            'text-max-width': '64px',
            'border-width': 2,
            'border-color': '#ffffff40',
          },
        },
        {
          // Focal node — larger, gold ring
          selector: 'node[?isFocal]',
          style: {
            width: 96,
            height: 96,
            'font-size': '13px',
            'border-width': 4,
            'border-color': '#FFD700',
          },
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 4,
            'border-color': '#FFD700',
            'overlay-opacity': 0.2,
            'overlay-color': '#FFD700',
          },
        },
        {
          selector: 'edge',
          style: {
            width: 2,
            'line-color': '#666',
            'target-arrow-color': '#666',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'arrow-scale': 1.2,
            opacity: 0.7,
          },
        },
        ...ALL_EDGE_TYPES.map(et => ({
          selector: `edge[type="${et}"]`,
          style: {
            'line-color': EDGE_COLORS[et],
            'target-arrow-color': EDGE_COLORS[et],
            'line-style': et === 'registers_blueprint' ? 'dashed' : 'solid',
          } as any,
        })),
      ],
      layout: {
        name: 'dagre',
        rankDir: 'TB',
        nodeSep: 60,
        rankSep: 80,
        padding: 40,
        animate: false,
      } as any,
    });

    // Click node → set as new focal or open sidebar
    cy.on('tap', 'node', evt => {
      const nodeId = evt.target.id();
      const graphNode = graph.nodes.find(n => n.id === nodeId);
      if (graphNode) {
        onNodeSelect(graphNode as Node);
      }
    });

    // Double-click → re-focal
    cy.on('dblclick', 'node', evt => {
      const nodeId = evt.target.id();
      const graphNode = graph.nodes.find(n => n.id === nodeId);
      if (graphNode) selectFocal(graphNode);
    });

    cyRef.current = cy;

    return () => {
      cy.destroy();
    };
  }, [neighborhood, focalNodeId, graph.nodes, onNodeSelect, selectFocal]);

  // Highlight selected node from sidebar without rebuilding
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes().unselect();
    if (selectedNodeId) {
      cy.$(`#${CSS.escape(selectedNodeId)}`).select();
    }
  }, [selectedNodeId]);

  // ── Toggle helpers ───────────────────────────────────────────────────────
  const toggleNodeType = (t: NodeTypeKey) => {
    setVisibleNodeTypes(prev => {
      const next = new Set(prev);
      if (next.has(t)) {
        if (next.size > 1) next.delete(t); // keep at least one
      } else {
        next.add(t);
      }
      return next;
    });
  };

  const toggleEdgeType = (t: EdgeTypeKey) => {
    setVisibleEdgeTypes(prev => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });
  };

  const fitGraph = () => cyRef.current?.fit(undefined, 40);
  const resetFocal = () => {
    setFocalNodeId(null);
    setFocalNode(null);
    setSearchQuery('');
  };

  // ─── Render ──────────────────────────────────────────────────────────────
  return (
    <div className="w-full h-full flex flex-col bg-gray-50 dark:bg-gray-900">
      {/* ── Toolbar ── */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-4 py-3 flex flex-wrap items-center gap-3">

        {/* Search box */}
        <div className="relative flex-1 min-w-[220px] max-w-sm">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            onFocus={() => searchResults.length > 0 && setShowResults(true)}
            placeholder="Search nodes (e.g. User, auth, contractors)…"
            className="w-full pl-9 pr-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          {showResults && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg shadow-xl z-50 max-h-72 overflow-y-auto">
              {searchResults.map(n => (
                <button
                  key={n.id}
                  onMouseDown={() => selectFocal(n)}
                  className="w-full text-left px-3 py-2 hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2 text-sm"
                >
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: NODE_COLORS[n.type as NodeTypeKey] || '#999' }}
                  />
                  <span className="font-medium text-gray-900 dark:text-white truncate">{n.label}</span>
                  <span className="text-xs text-gray-400 shrink-0">{n.type}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Focal node badge */}
        {focalNode && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium text-white"
            style={{ backgroundColor: NODE_COLORS[focalNode.type as NodeTypeKey] || '#555' }}>
            <span className="opacity-75 text-xs">{focalNode.type}</span>
            <span>{focalNode.label}</span>
            <button onClick={resetFocal} className="ml-1 opacity-70 hover:opacity-100">✕</button>
          </div>
        )}

        {/* Depth slider */}
        <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
          <span className="whitespace-nowrap">Hops:</span>
          <input
            type="range" min={1} max={4} value={depth}
            onChange={e => setDepth(Number(e.target.value))}
            className="w-20 accent-blue-600"
          />
          <span className="w-4 text-center font-bold text-blue-600 dark:text-blue-400">{depth}</span>
        </label>

        {/* Fit button */}
        <button
          onClick={fitGraph}
          title="Fit to screen"
          className="p-1.5 rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
          </svg>
        </button>

        {/* Stats */}
        {focalNode && (
          <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
            {neighborhoodStats.nodes} nodes · {neighborhoodStats.edges} edges
          </span>
        )}
      </div>

      {/* ── Second row: node type + edge type toggles ── */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-4 py-2 flex flex-wrap items-center gap-x-4 gap-y-1">
        {/* Node types */}
        <span className="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wide mr-1">Show:</span>
        {ALL_NODE_TYPES.map(t => (
          <button
            key={t}
            onClick={() => toggleNodeType(t)}
            className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium transition-opacity ${
              visibleNodeTypes.has(t) ? 'opacity-100' : 'opacity-30'
            }`}
            style={{
              backgroundColor: visibleNodeTypes.has(t)
                ? NODE_COLORS[t] + '22'
                : '#88888822',
              color: NODE_COLORS[t],
              border: `1px solid ${NODE_COLORS[t]}66`,
            }}
          >
            <span
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: NODE_COLORS[t] }}
            />
            {NODE_TYPE_LABELS[t]}
          </button>
        ))}

        <span className="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wide mx-1">Edges:</span>
        {ALL_EDGE_TYPES.map(t => (
          <button
            key={t}
            onClick={() => toggleEdgeType(t)}
            className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium transition-opacity ${
              visibleEdgeTypes.has(t) ? 'opacity-100' : 'opacity-30'
            }`}
            style={{
              backgroundColor: visibleEdgeTypes.has(t)
                ? EDGE_COLORS[t] + '22'
                : '#88888822',
              color: EDGE_COLORS[t],
              border: `1px solid ${EDGE_COLORS[t]}66`,
            }}
          >
            <span
              className="w-5 h-0.5 inline-block"
              style={{ backgroundColor: EDGE_COLORS[t] }}
            />
            {EDGE_TYPE_LABELS[t]}
          </button>
        ))}
      </div>

      {/* ── Canvas or empty state ── */}
      <div className="flex-1 relative overflow-hidden">
        {!focalNode ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-8">
            <div className="text-6xl mb-4">🔭</div>
            <h2 className="text-xl font-semibold text-gray-700 dark:text-gray-300 mb-2">
              Search for a node to explore
            </h2>
            <p className="text-gray-500 dark:text-gray-500 max-w-sm text-sm mb-6">
              Type a model, route, blueprint, action, or service name above. Click any result to load its neighborhood graph.
            </p>
            <div className="flex flex-wrap justify-center gap-2 text-xs">
              {(['model::User', 'blueprint::auth', 'action::contractor_detail', 'model::Contractor'] as const).map(hint => (
                <button
                  key={hint}
                  onMouseDown={() => {
                    const n = graph.nodes.find(nd => nd.id === hint);
                    if (n) selectFocal(n);
                  }}
                  className="px-3 py-1.5 rounded-full border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-blue-400 hover:text-blue-500 transition-colors"
                >
                  {hint}
                </button>
              ))}
            </div>
            <p className="mt-4 text-xs text-gray-400 dark:text-gray-600">
              Double-click any node in the graph to re-center on it · Single-click to open the details sidebar
            </p>
          </div>
        ) : (
          <div ref={containerRef} className="w-full h-full" />
        )}
      </div>
    </div>
  );
}
