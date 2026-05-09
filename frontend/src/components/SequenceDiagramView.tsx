import { useState, useMemo } from 'react';
import type { Graph, Node, Edge, DBOperation } from '../types/graph';
import { NODE_COLORS } from '../utils/cytoscapeStyles';

interface SequenceDiagramViewProps {
  graph: Graph;
  onNodeSelect: (node: Node | null) => void;
  selectedNodeId: string | null;
}

interface Lifeline {
  id: string;
  label: string;
  type: 'client' | 'blueprint' | 'route' | 'action' | 'model';
  color: string;
}

interface Message {
  from: number; // lifeline index
  to: number;   // lifeline index
  label: string;
  isReturn: boolean; // dashed arrow going left
  activationStart?: boolean;
  activationEnd?: boolean;
}

// Route info with blueprint context
interface RouteInfo {
  node: Node;
  blueprint: Node | null;
  blueprintName: string;
}

export function SequenceDiagramView({ graph, onNodeSelect, selectedNodeId }: SequenceDiagramViewProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [blueprintFilter, setBlueprintFilter] = useState<string>('all');

  // Build route list with blueprint info
  const routes = useMemo<RouteInfo[]>(() => {
    const routeNodes = graph.nodes.filter(n => n.type === 'route');
    const edgeMap = new Map<string, Edge[]>();
    
    graph.edges.forEach(e => {
      if (!edgeMap.has(e.target)) edgeMap.set(e.target, []);
      edgeMap.get(e.target)!.push(e);
    });

    return routeNodes.map(route => {
      const blueprintEdge = edgeMap.get(route.id)?.find(e => e.type === 'registers_blueprint');
      const blueprint = blueprintEdge ? graph.nodes.find(n => n.id === blueprintEdge.source) || null : null;
      const blueprintName = blueprint?.label || route.metadata?.blueprint || 'No Blueprint';
      
      return { node: route, blueprint, blueprintName };
    }).sort((a, b) => {
      // Sort by blueprint, then by route path
      const bpCompare = a.blueprintName.localeCompare(b.blueprintName);
      if (bpCompare !== 0) return bpCompare;
      return a.node.label.localeCompare(b.node.label);
    });
  }, [graph]);

  // Get unique blueprint names for filter
  const blueprints = useMemo(() => {
    const names = new Set(routes.map(r => r.blueprintName));
    return Array.from(names).sort();
  }, [routes]);

  // Filter routes
  const filteredRoutes = useMemo(() => {
    return routes.filter(r => {
      const matchesSearch = searchTerm === '' || 
        r.node.label.toLowerCase().includes(searchTerm.toLowerCase()) ||
        r.blueprintName.toLowerCase().includes(searchTerm.toLowerCase()) ||
        r.node.metadata?.view_function?.toLowerCase().includes(searchTerm.toLowerCase());
      
      const matchesBlueprint = blueprintFilter === 'all' || r.blueprintName === blueprintFilter;
      
      return matchesSearch && matchesBlueprint;
    });
  }, [routes, searchTerm, blueprintFilter]);

  // Select first route by default or find selected route
  const selectedRoute = useMemo(() => {
    if (selectedNodeId) {
      const found = filteredRoutes.find(r => r.node.id === selectedNodeId);
      if (found) return found;
    }
    return filteredRoutes[0] || null;
  }, [filteredRoutes, selectedNodeId]);

  // Build sequence diagram data for selected route
  const { lifelines, messages } = useMemo(() => {
    if (!selectedRoute) return { lifelines: [], messages: [] };

    const route = selectedRoute.node;
    const blueprint = selectedRoute.blueprint;
    
    const lifelines: Lifeline[] = [];
    const messages: Message[] = [];
    
    // Always start with Client
    lifelines.push({
      id: '__client__',
      label: 'Client',
      type: 'client',
      color: '#6B7280'
    });

    // Add blueprint if exists
    if (blueprint) {
      lifelines.push({
        id: blueprint.id,
        label: blueprint.label,
        type: 'blueprint',
        color: NODE_COLORS.blueprint
      });
    }

    // Add route
    lifelines.push({
      id: route.id,
      label: route.label,
      type: 'route',
      color: NODE_COLORS.route
    });

    const lifelineIndexMap = new Map<string, number>();
    lifelines.forEach((ll, idx) => lifelineIndexMap.set(ll.id, idx));

    // Find actions called by this route
    const actionEdges = graph.edges.filter(e => 
      e.source === route.id && e.type === 'calls'
    );

    const actions = actionEdges.map(e => 
      graph.nodes.find(n => n.id === e.target)
    ).filter((n): n is Node => n !== undefined);

    // Add action lifelines
    actions.forEach(action => {
      lifelines.push({
        id: action.id,
        label: action.label,
        type: 'action',
        color: NODE_COLORS.action
      });
      lifelineIndexMap.set(action.id, lifelines.length - 1);
    });

    // Find models used by actions
    const modelIds = new Set<string>();
    const modelNodes: Node[] = [];
    
    actions.forEach(action => {
      const modelEdges = graph.edges.filter(e => 
        e.source === action.id && e.type === 'uses_model'
      );
      modelEdges.forEach(e => {
        if (!modelIds.has(e.target)) {
          modelIds.add(e.target);
          const model = graph.nodes.find(n => n.id === e.target);
          if (model) modelNodes.push(model);
        }
      });
    });

    // Add model lifelines
    modelNodes.forEach(model => {
      lifelines.push({
        id: model.id,
        label: model.label,
        type: 'model',
        color: NODE_COLORS.model
      });
      lifelineIndexMap.set(model.id, lifelines.length - 1);
    });

    // Build messages
    const clientIdx = 0;
    const method = route.metadata?.methods?.[0] || 'GET';
    
    // Client → Blueprint (if exists) or Route
    if (blueprint) {
      const bpIdx = lifelineIndexMap.get(blueprint.id)!;
      messages.push({
        from: clientIdx,
        to: bpIdx,
        label: `HTTP ${method} ${route.label}`,
        isReturn: false,
        activationStart: true
      });

      // Blueprint → Route
      const routeIdx = lifelineIndexMap.get(route.id)!;
      messages.push({
        from: bpIdx,
        to: routeIdx,
        label: 'dispatch()',
        isReturn: false,
        activationStart: true
      });
    } else {
      // Client → Route directly
      const routeIdx = lifelineIndexMap.get(route.id)!;
      messages.push({
        from: clientIdx,
        to: routeIdx,
        label: `HTTP ${method} ${route.label}`,
        isReturn: false,
        activationStart: true
      });
    }

    // Route → Actions → Models
    actions.forEach(action => {
      const routeIdx = lifelineIndexMap.get(route.id)!;
      const actionIdx = lifelineIndexMap.get(action.id)!;
      
      messages.push({
        from: routeIdx,
        to: actionIdx,
        label: `${action.label}()`,
        isReturn: false,
        activationStart: true
      });

      // Action → Models
      const modelEdges = graph.edges.filter(e => 
        e.source === action.id && e.type === 'uses_model'
      );
      
      modelEdges.forEach(edge => {
        const modelIdx = lifelineIndexMap.get(edge.target);
        if (modelIdx !== undefined) {
          const model = graph.nodes.find(n => n.id === edge.target);
          const dbOps = action.metadata?.db_operations || [];
          const label = getModelOperationLabel(model?.label || 'Model', dbOps);
          
          messages.push({
            from: actionIdx,
            to: modelIdx,
            label,
            isReturn: false,
            activationStart: true
          });

          messages.push({
            from: modelIdx,
            to: actionIdx,
            label: 'result',
            isReturn: true,
            activationEnd: true
          });
        }
      });

      // Action → Route return
      messages.push({
        from: actionIdx,
        to: routeIdx,
        label: 'response data',
        isReturn: true,
        activationEnd: true
      });
    });

    // If no actions, route still returns
    if (actions.length === 0) {
      const routeIdx = lifelineIndexMap.get(route.id)!;
      messages.push({
        from: routeIdx,
        to: clientIdx,
        label: 'HTTP 200',
        isReturn: true,
        activationEnd: true
      });
    } else {
      // Route → Client return
      const routeIdx = lifelineIndexMap.get(route.id)!;
      if (blueprint) {
        const bpIdx = lifelineIndexMap.get(blueprint.id)!;
        messages.push({
          from: routeIdx,
          to: bpIdx,
          label: 'response data',
          isReturn: true,
          activationEnd: true
        });
        messages.push({
          from: bpIdx,
          to: clientIdx,
          label: 'HTTP 200',
          isReturn: true,
          activationEnd: true
        });
      } else {
        messages.push({
          from: routeIdx,
          to: clientIdx,
          label: 'HTTP 200',
          isReturn: true,
          activationEnd: true
        });
      }
    }

    return { lifelines, messages };
  }, [selectedRoute, graph]);

  const handleExportPNG = () => {
    const svg = document.getElementById('sequence-diagram-svg');
    if (!svg) return;

    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const svgData = new XMLSerializer().serializeToString(svg);
    const img = new Image();
    
    img.onload = () => {
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.fillStyle = 'white';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0);
      
      canvas.toBlob(blob => {
        if (!blob) return;
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `sequence-${selectedRoute?.node.label.replace(/[^a-zA-Z0-9]/g, '-')}.png`;
        a.click();
        URL.revokeObjectURL(url);
      });
    };

    img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgData)));
  };

  return (
    <div className="flex h-full bg-white dark:bg-gray-900">
      {/* Left panel - Route selector */}
      <div className="w-80 border-r border-gray-200 dark:border-gray-700 flex flex-col">
        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
            Select Route
          </h3>
          
          {/* Search */}
          <input
            type="text"
            placeholder="Search routes..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />

          {/* Blueprint filter */}
          <select
            value={blueprintFilter}
            onChange={e => setBlueprintFilter(e.target.value)}
            className="w-full mt-2 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Blueprints</option>
            {blueprints.map(bp => (
              <option key={bp} value={bp}>{bp}</option>
            ))}
          </select>

          <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
            {filteredRoutes.length} route{filteredRoutes.length !== 1 ? 's' : ''}
          </div>
        </div>

        {/* Route list */}
        <div className="flex-1 overflow-y-auto">
          {filteredRoutes.map(route => (
            <button
              key={route.node.id}
              onClick={() => onNodeSelect(route.node)}
              className={`w-full text-left px-4 py-3 border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors ${
                selectedRoute?.node.id === route.node.id
                  ? 'bg-blue-50 dark:bg-blue-900/20 border-l-4 border-l-blue-500'
                  : ''
              }`}
            >
              <div className="text-xs font-semibold text-gray-500 dark:text-gray-400 mb-1">
                {route.blueprintName}
              </div>
              <div className="text-sm font-mono text-gray-900 dark:text-white break-all">
                {route.node.label}
              </div>
              {route.node.metadata?.view_function && (
                <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {route.node.metadata.view_function}
                </div>
              )}
              <div className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                {route.node.metadata?.methods?.join(', ') || 'GET'}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Right panel - Diagram */}
      <div className="flex-1 flex flex-col">
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
              UML Sequence Diagram
            </h3>
            {selectedRoute && (
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 font-mono">
                {selectedRoute.node.label}
              </p>
            )}
          </div>
          
          <button
            onClick={handleExportPNG}
            disabled={!selectedRoute}
            className="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
          >
            Export PNG
          </button>
        </div>

        <div className="flex-1 overflow-auto p-8">
          {!selectedRoute ? (
            <div className="flex items-center justify-center h-full text-gray-400 dark:text-gray-500">
              Select a route to view its sequence diagram
            </div>
          ) : (
            <SequenceDiagramSVG lifelines={lifelines} messages={messages} />
          )}
        </div>
      </div>
    </div>
  );
}

// Helper to determine model operation label
function getModelOperationLabel(_modelName: string, dbOps: DBOperation[]): string {
  if (dbOps.length === 0) return 'query()';
  
  const hasWrite = dbOps.some(op => op.type === 'WRITE');
  const hasRead = dbOps.some(op => op.type === 'READ');
  
  if (hasWrite && hasRead) return 'query() / save()';
  if (hasWrite) return 'save() / update()';
  return 'query()';
}

// SVG rendering component
interface SequenceDiagramSVGProps {
  lifelines: Lifeline[];
  messages: Message[];
}

function SequenceDiagramSVG({ lifelines, messages }: SequenceDiagramSVGProps) {
  const LIFELINE_SPACING = 180;
  const LIFELINE_BOX_WIDTH = 160;
  const LIFELINE_BOX_HEIGHT = 50;
  const MESSAGE_ROW_HEIGHT = 60;
  const START_Y = 100;
  const PADDING = 50;
  const ACTIVATION_WIDTH = 10;

  const width = lifelines.length * LIFELINE_SPACING + PADDING * 2;
  const height = START_Y + messages.length * MESSAGE_ROW_HEIGHT + 80;

  // Track activation state for each lifeline
  const activations = new Map<number, Array<[number, number]>>(); // lifeline index → [start_y, end_y][]

  let currentY = START_Y;
  messages.forEach((msg) => {
    if (msg.activationStart) {
      if (!activations.has(msg.to)) activations.set(msg.to, []);
      activations.get(msg.to)!.push([currentY, currentY]);
    }
    if (msg.activationEnd) {
      const acts = activations.get(msg.from);
      if (acts && acts.length > 0) {
        acts[acts.length - 1][1] = currentY;
      }
    }
    currentY += MESSAGE_ROW_HEIGHT;
  });

  return (
    <svg
      id="sequence-diagram-svg"
      width={width}
      height={height}
      className="mx-auto"
      style={{ minWidth: width }}
    >
      {/* Lifelines */}
      {lifelines.map((ll, idx) => {
        const x = PADDING + idx * LIFELINE_SPACING;
        const boxX = x - LIFELINE_BOX_WIDTH / 2;
        const boxY = 20;

        return (
          <g key={ll.id}>
            {/* Lifeline box */}
            <rect
              x={boxX}
              y={boxY}
              width={LIFELINE_BOX_WIDTH}
              height={LIFELINE_BOX_HEIGHT}
              fill={ll.color}
              stroke="#333"
              strokeWidth={2}
              rx={4}
            />
            <text
              x={x}
              y={boxY + LIFELINE_BOX_HEIGHT / 2}
              textAnchor="middle"
              dominantBaseline="middle"
              fill="white"
              fontSize="12"
              fontWeight="bold"
              className="select-none"
            >
              {truncateLabel(ll.label, 20)}
            </text>

            {/* Dashed vertical line */}
            <line
              x1={x}
              y1={boxY + LIFELINE_BOX_HEIGHT}
              x2={x}
              y2={height - 20}
              stroke="#999"
              strokeWidth={1}
              strokeDasharray="4,4"
            />

            {/* Activation boxes */}
            {activations.get(idx)?.map((act, actIdx) => (
              <rect
                key={actIdx}
                x={x - ACTIVATION_WIDTH / 2}
                y={act[0]}
                width={ACTIVATION_WIDTH}
                height={act[1] - act[0]}
                fill="white"
                stroke="#333"
                strokeWidth={1}
              />
            ))}
          </g>
        );
      })}

      {/* Messages */}
      {messages.map((msg, idx) => {
        const y = START_Y + idx * MESSAGE_ROW_HEIGHT;
        const fromX = PADDING + msg.from * LIFELINE_SPACING;
        const toX = PADDING + msg.to * LIFELINE_SPACING;

        return (
          <g key={idx}>
            {/* Arrow line */}
            <line
              x1={fromX}
              y1={y}
              x2={toX}
              y2={y}
              stroke={msg.isReturn ? '#666' : '#000'}
              strokeWidth={msg.isReturn ? 1 : 2}
              strokeDasharray={msg.isReturn ? '4,4' : '0'}
              markerEnd={`url(#arrow-${msg.isReturn ? 'return' : 'call'})`}
            />

            {/* Label */}
            <text
              x={(fromX + toX) / 2}
              y={y - 8}
              textAnchor="middle"
              fontSize="11"
              fill="#333"
              className="select-none dark:fill-white"
            >
              {truncateLabel(msg.label, 30)}
            </text>
          </g>
        );
      })}

      {/* Arrow markers */}
      <defs>
        <marker
          id="arrow-call"
          markerWidth="10"
          markerHeight="10"
          refX="9"
          refY="3"
          orient="auto"
          markerUnits="strokeWidth"
        >
          <path d="M0,0 L0,6 L9,3 z" fill="#000" />
        </marker>
        <marker
          id="arrow-return"
          markerWidth="10"
          markerHeight="10"
          refX="9"
          refY="3"
          orient="auto"
          markerUnits="strokeWidth"
        >
          <path d="M0,0 L0,6 L9,3 z" fill="#666" />
        </marker>
      </defs>
    </svg>
  );
}

function truncateLabel(label: string, maxLen: number): string {
  if (label.length <= maxLen) return label;
  return label.substring(0, maxLen - 3) + '...';
}
