import { useState, useMemo } from 'react';
import type { Graph, Node } from '../types/graph';

interface ComponentDiagramProps {
  graph: Graph;
  onNodeSelect: (node: Node | null) => void;
  selectedNodeId: string | null;
}

interface BlueprintComponent {
  id: string;
  label: string;
  urlPrefix?: string;
  routeCount: number;
  modelIds: Set<string>;
  modelCount: number;
  x: number;
  y: number;
}

interface Dependency {
  from: string;
  to: string;
  sharedCount: number;
}

const COMPONENT_WIDTH = 220;
const COMPONENT_HEIGHT = 100;
const HORIZONTAL_GAP = 120;
const VERTICAL_GAP = 120;

export function ComponentDiagram({ graph, onNodeSelect, selectedNodeId }: ComponentDiagramProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [showDependencies, setShowDependencies] = useState(true);
  const [minModels, setMinModels] = useState(0);
  const [zoom, setZoom] = useState(1);

  // Compute blueprint components with their model dependencies
  const components = useMemo(() => {
    const blueprints = graph.nodes.filter(n => n.type === 'blueprint');
    
    const comps: BlueprintComponent[] = blueprints.map(bp => {
      // Find routes registered by this blueprint
      const routeEdges = graph.edges.filter(e => e.source === bp.id && e.type === 'registers_blueprint');
      const routeIds = routeEdges.map(e => e.target);

      // Find models touched by this blueprint (transitively)
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

      return {
        id: bp.id,
        label: bp.label,
        urlPrefix: bp.metadata.url_prefix,
        routeCount: routeIds.length,
        modelIds,
        modelCount: modelIds.size,
        x: 0,
        y: 0,
      };
    });

    // Sort by model count descending (most connected first)
    comps.sort((a, b) => b.modelCount - a.modelCount);

    // Layout in grid
    const cols = Math.ceil(Math.sqrt(comps.length));
    comps.forEach((comp, idx) => {
      const col = idx % cols;
      const row = Math.floor(idx / cols);
      comp.x = col * (COMPONENT_WIDTH + HORIZONTAL_GAP) + 50;
      comp.y = row * (COMPONENT_HEIGHT + VERTICAL_GAP) + 50;
    });

    return comps;
  }, [graph]);

  // Compute dependencies (pairs of blueprints sharing models)
  const dependencies = useMemo(() => {
    const deps: Dependency[] = [];
    
    for (let i = 0; i < components.length; i++) {
      for (let j = i + 1; j < components.length; j++) {
        const compA = components[i];
        const compB = components[j];
        
        // Find shared models
        const shared = [...compA.modelIds].filter(modelId => compB.modelIds.has(modelId));
        
        if (shared.length > 0) {
          deps.push({
            from: compA.id,
            to: compB.id,
            sharedCount: shared.length,
          });
        }
      }
    }
    
    return deps;
  }, [components]);

  // Filter components
  const filteredComponents = useMemo(() => {
    return components.filter(comp => {
      if (comp.modelCount < minModels) return false;
      if (searchQuery && !comp.label.toLowerCase().includes(searchQuery.toLowerCase())) return false;
      return true;
    });
  }, [components, searchQuery, minModels]);

  // Compute SVG dimensions
  const svgWidth = useMemo(() => {
    if (filteredComponents.length === 0) return 800;
    return Math.max(...filteredComponents.map(c => c.x + COMPONENT_WIDTH)) + 50;
  }, [filteredComponents]);

  const svgHeight = useMemo(() => {
    if (filteredComponents.length === 0) return 600;
    return Math.max(...filteredComponents.map(c => c.y + COMPONENT_HEIGHT)) + 50;
  }, [filteredComponents]);

  // Handle component click
  const handleComponentClick = (comp: BlueprintComponent) => {
    const node = graph.nodes.find(n => n.id === comp.id);
    if (node) onNodeSelect(node);
  };

  // Zoom controls
  const handleZoomIn = () => setZoom(prev => Math.min(prev + 0.2, 3));
  const handleZoomOut = () => setZoom(prev => Math.max(prev - 0.2, 0.3));
  const handleZoomReset = () => setZoom(1);

  return (
    <div className="w-full h-full flex flex-col bg-gray-50 dark:bg-gray-900">
      {/* Controls toolbar */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4">
        <div className="flex flex-wrap items-center gap-4">
          {/* Search */}
          <div className="flex-1 min-w-[200px]">
            <input
              type="text"
              placeholder="Search blueprints..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </div>

          {/* Show Dependencies toggle */}
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={showDependencies}
              onChange={(e) => setShowDependencies(e.target.checked)}
              className="w-4 h-4 text-teal-600 bg-gray-100 dark:bg-gray-700 border-gray-300 dark:border-gray-600 rounded focus:ring-teal-500"
            />
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Show Dependencies
            </span>
          </label>

          {/* Min models filter */}
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Min models:
            </label>
            <input
              type="number"
              min="0"
              value={minModels}
              onChange={(e) => setMinModels(Math.max(0, parseInt(e.target.value) || 0))}
              className="w-16 px-2 py-1 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </div>

          {/* Count badge */}
          <div className="px-3 py-1 bg-teal-100 dark:bg-teal-900 text-teal-800 dark:text-teal-200 rounded-full text-sm font-semibold">
            {filteredComponents.length} components
          </div>

          {/* Zoom controls */}
          <div className="flex items-center gap-1 border-l border-gray-300 dark:border-gray-600 pl-4">
            <button
              onClick={handleZoomOut}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
              title="Zoom out"
            >
              <svg className="w-4 h-4 text-gray-700 dark:text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM13 10H7" />
              </svg>
            </button>
            <button
              onClick={handleZoomReset}
              className="px-2 py-1 text-xs font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
              title="Reset zoom"
            >
              {Math.round(zoom * 100)}%
            </button>
            <button
              onClick={handleZoomIn}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
              title="Zoom in"
            >
              <svg className="w-4 h-4 text-gray-700 dark:text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v6m3-3H7" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* SVG canvas */}
      <div className="flex-1 overflow-auto">
        <svg
          width={svgWidth * zoom}
          height={svgHeight * zoom}
          className="bg-white dark:bg-gray-900"
        >
          <defs>
            <marker id="dep-arrow" markerWidth="8" markerHeight="8" refX="7" refY="2.5" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L0,5 L7,2.5 z" fill="#009688" fillOpacity="0.7" />
            </marker>
          </defs>
          <g transform={`scale(${zoom})`}>
            {/* Dependency arrows (curved bezier) */}
            {showDependencies && dependencies.map((dep, idx) => {
              const fromComp = filteredComponents.find(c => c.id === dep.from);
              const toComp = filteredComponents.find(c => c.id === dep.to);
              if (!fromComp || !toComp) return null;

              const sc = { x: fromComp.x + COMPONENT_WIDTH / 2, y: fromComp.y + COMPONENT_HEIGHT / 2 };
              const tc = { x: toComp.x + COMPONENT_WIDTH / 2,   y: toComp.y + COMPONENT_HEIGHT / 2 };
              const dx = tc.x - sc.x;
              const dy = tc.y - sc.y;
              const absDx = Math.abs(dx);
              const absDy = Math.abs(dy);
              const stagger = (idx % 5 - 2) * 14;

              let sx, sy, ex, ey, d;
              if (absDx >= absDy) {
                sx = dx > 0 ? fromComp.x + COMPONENT_WIDTH : fromComp.x;
                sy = sc.y + stagger;
                ex = dx > 0 ? toComp.x : toComp.x + COMPONENT_WIDTH;
                ey = tc.y + stagger;
                const cp = Math.max(60, absDx * 0.4);
                d = `M ${sx} ${sy} C ${sx + (dx > 0 ? cp : -cp)} ${sy}, ${ex + (dx > 0 ? -cp : cp)} ${ey}, ${ex} ${ey}`;
              } else {
                sx = sc.x + stagger;
                sy = dy > 0 ? fromComp.y + COMPONENT_HEIGHT : fromComp.y;
                ex = tc.x + stagger;
                ey = dy > 0 ? toComp.y : toComp.y + COMPONENT_HEIGHT;
                const cp = Math.max(60, absDy * 0.4);
                d = `M ${sx} ${sy} C ${sx} ${sy + (dy > 0 ? cp : -cp)}, ${ex} ${ey + (dy > 0 ? -cp : cp)}, ${ex} ${ey}`;
              }
              const midX = (sx + ex) / 2;
              const midY = (sy + ey) / 2;

              return (
                <g key={`dep-${idx}`}>
                  <path d={d} fill="none" stroke="#009688" strokeWidth="1.5" strokeDasharray="6 3" opacity="0.55" markerEnd="url(#dep-arrow)" />
                  <rect x={midX - 22} y={midY - 9} width={44} height={16} fill="white" fillOpacity="0.88" rx="3" />
                  <text x={midX} y={midY + 3} fontSize="9" fill="#009688" textAnchor="middle" className="pointer-events-none">
                    {dep.sharedCount} shared
                  </text>
                </g>
              );
            })}

            {/* Component boxes */}
            {filteredComponents.map(comp => {
              const isSelected = comp.id === selectedNodeId;

              return (
                <g
                  key={comp.id}
                  transform={`translate(${comp.x}, ${comp.y})`}
                  onClick={() => handleComponentClick(comp)}
                  className="cursor-pointer"
                >
                  {/* Main box */}
                  <rect
                    width={COMPONENT_WIDTH}
                    height={COMPONENT_HEIGHT}
                    fill="white"
                    stroke={isSelected ? '#FFD700' : '#009688'}
                    strokeWidth={isSelected ? 3 : 2}
                    rx="4"
                    className="transition-all hover:stroke-[#00796B]"
                  />

                  {/* UML component icon (top-right) */}
                  <g transform={`translate(${COMPONENT_WIDTH - 24}, 8)`}>
                    <rect width="16" height="12" fill="none" stroke="#009688" strokeWidth="1.5" />
                    <rect x="2" y="2" width="4" height="3" fill="#009688" />
                    <rect x="10" y="2" width="4" height="3" fill="#009688" />
                  </g>

                  {/* Stereotype */}
                  <text
                    x={COMPONENT_WIDTH / 2}
                    y={20}
                    fontSize="10"
                    fill="#666"
                    textAnchor="middle"
                    className="pointer-events-none"
                  >
                    «component»
                  </text>

                  {/* Blueprint name */}
                  <text
                    x={COMPONENT_WIDTH / 2}
                    y={40}
                    fontSize="14"
                    fontWeight="bold"
                    fill="#1a1a1a"
                    textAnchor="middle"
                    className="pointer-events-none"
                  >
                    {comp.label.length > 20 ? comp.label.substring(0, 18) + '...' : comp.label}
                  </text>

                  {/* URL prefix (if present) */}
                  {comp.urlPrefix && (
                    <text
                      x={COMPONENT_WIDTH / 2}
                      y={55}
                      fontSize="9"
                      fill="#666"
                      textAnchor="middle"
                      className="pointer-events-none"
                    >
                      {comp.urlPrefix}
                    </text>
                  )}

                  {/* Separator line */}
                  <line
                    x1={10}
                    y1={comp.urlPrefix ? 62 : 50}
                    x2={COMPONENT_WIDTH - 10}
                    y2={comp.urlPrefix ? 62 : 50}
                    stroke="#ccc"
                    strokeWidth="1"
                  />

                  {/* Stats */}
                  <text
                    x={COMPONENT_WIDTH / 2}
                    y={comp.urlPrefix ? 77 : 68}
                    fontSize="11"
                    fill="#333"
                    textAnchor="middle"
                    className="pointer-events-none"
                  >
                    {comp.routeCount} routes
                  </text>
                  <text
                    x={COMPONENT_WIDTH / 2}
                    y={comp.urlPrefix ? 92 : 83}
                    fontSize="11"
                    fill="#333"
                    textAnchor="middle"
                    className="pointer-events-none"
                  >
                    touches {comp.modelCount} models
                  </text>
                </g>
              );
            })}
          </g>
        </svg>
      </div>
    </div>
  );
}
