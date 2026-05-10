import { useState, useMemo } from 'react';
import { NODE_COLORS } from '../utils/cytoscapeStyles';
import type { Node, Graph } from '../types/graph';

interface BlueprintDrillDownProps {
  graph: Graph;
  onNodeSelect: (node: Node | null) => void;
  selectedNodeId: string | null;
}

interface BlueprintSubgraph {
  blueprint: Node;
  routes: Node[];
  actions: Node[];
  services: Node[];
  models: Node[];
}

export function BlueprintDrillDown({ graph, onNodeSelect, selectedNodeId }: BlueprintDrillDownProps) {
  const [selectedBlueprintId, setSelectedBlueprintId] = useState<string | null>(null);
  const [collapsedSections, setCollapsedSections] = useState<Set<string>>(new Set());

  // Extract all blueprint nodes with route counts
  const blueprints = useMemo(() => {
    const blueprintNodes = graph.nodes.filter(n => n.type === 'blueprint');
    
    return blueprintNodes
      .map(bp => {
        const routeCount = graph.nodes.filter(
          n => n.type === 'route' && n.metadata.blueprint === bp.label
        ).length;
        return { node: bp, routeCount };
      })
      .sort((a, b) => a.node.label.localeCompare(b.node.label));
  }, [graph.nodes]);

  // Compute the subgraph for the selected blueprint
  const subgraph = useMemo((): BlueprintSubgraph | null => {
    if (!selectedBlueprintId) return null;

    const blueprint = graph.nodes.find(n => n.id === selectedBlueprintId);
    if (!blueprint) return null;

    // Find all routes belonging to this blueprint
    const routes = graph.nodes.filter(
      n => n.type === 'route' && n.metadata.blueprint === blueprint.label
    );
    const routeIds = new Set(routes.map(r => r.id));

    // Find actions called by those routes
    const actionIds = new Set(
      graph.edges
        .filter(e => routeIds.has(e.source) && e.type === 'calls')
        .map(e => e.target)
    );
    const actions = graph.nodes.filter(n => actionIds.has(n.id) && n.type === 'action');

    // Find services called by those actions
    const serviceIds = new Set(
      graph.edges
        .filter(e => actionIds.has(e.source) && e.type === 'calls')
        .map(e => e.target)
    );
    const services = graph.nodes.filter(n => serviceIds.has(n.id) && n.type === 'service');

    // Find models used by routes, actions, or services
    const allSourceIds = new Set([...routeIds, ...actionIds, ...serviceIds]);
    const modelIds = new Set(
      graph.edges
        .filter(e => e.type === 'uses_model' && allSourceIds.has(e.source))
        .map(e => e.target)
    );
    const models = graph.nodes.filter(n => modelIds.has(n.id) && n.type === 'model');

    return { blueprint, routes, actions, services, models };
  }, [selectedBlueprintId, graph]);

  const handleBlueprintClick = (blueprint: Node) => {
    setSelectedBlueprintId(blueprint.id);
    onNodeSelect(blueprint);
  };

  const toggleSection = (section: string) => {
    setCollapsedSections(prev => {
      const next = new Set(prev);
      if (next.has(section)) {
        next.delete(section);
      } else {
        next.add(section);
      }
      return next;
    });
  };

  const renderNodeCard = (node: Node) => {
    const isSelected = node.id === selectedNodeId;
    return (
      <button
        key={node.id}
        onClick={() => onNodeSelect(node)}
        className={`text-left p-3 rounded-lg border transition-all ${
          isSelected
            ? 'ring-2 ring-blue-500 bg-gray-700 border-gray-600'
            : 'bg-gray-700 hover:bg-gray-600 border-gray-600'
        }`}
      >
        <div className="flex items-start gap-2">
          <span
            className="mt-0.5 w-3 h-3 rounded-full shrink-0"
            style={{ backgroundColor: NODE_COLORS[node.type] || '#888' }}
          />
          <div className="min-w-0 flex-1">
            <div className="font-medium text-white text-sm truncate">
              {node.label}
            </div>
            <div className="text-xs text-gray-400 mt-0.5 truncate">
              {node.file_path}:{node.line_number}
            </div>
          </div>
        </div>
      </button>
    );
  };

  const renderSection = (
    title: string,
    sectionKey: string,
    nodes: Node[],
    columns: number = 2
  ) => {
    const isCollapsed = collapsedSections.has(sectionKey);
    const gridClass = columns === 3 ? 'grid-cols-3' : columns === 2 ? 'grid-cols-2' : 'grid-cols-1';

    return (
      <div className="border border-gray-700 rounded-lg overflow-hidden">
        <button
          onClick={() => toggleSection(sectionKey)}
          className="w-full px-4 py-3 bg-gray-800 hover:bg-gray-750 flex items-center justify-between transition-colors"
        >
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold uppercase tracking-wide text-gray-300">
              {title}
            </span>
            <span className="text-xs px-2 py-0.5 rounded bg-gray-700 text-gray-400 font-medium">
              {nodes.length}
            </span>
          </div>
          <svg
            className={`w-5 h-5 text-gray-400 transition-transform ${
              isCollapsed ? '-rotate-90' : ''
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        {!isCollapsed && (
          <div className="p-4 bg-gray-850">
            {nodes.length === 0 ? (
              <div className="text-center py-6 text-gray-500">
                <p className="text-sm">None</p>
              </div>
            ) : (
              <div className={`grid ${gridClass} gap-2`}>
                {nodes.map(node => renderNodeCard(node))}
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="h-full flex bg-gray-900">
      {/* Left panel: Blueprint list */}
      <div className="w-80 bg-gray-800 border-r border-gray-700 flex flex-col">
        <div className="p-4 border-b border-gray-700">
          <h3 className="text-lg font-bold text-white">Blueprints</h3>
          <p className="text-xs text-gray-400 mt-1">
            {blueprints.length} blueprint{blueprints.length !== 1 ? 's' : ''}
          </p>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {blueprints.map(({ node: bp, routeCount }) => {
            const isActive = bp.id === selectedBlueprintId;

            return (
              <button
                key={bp.id}
                onClick={() => handleBlueprintClick(bp)}
                className={`w-full text-left p-3 rounded-lg border transition-all ${
                  isActive
                    ? 'bg-gray-700 border-blue-500'
                    : 'bg-gray-750 border-gray-700 hover:bg-gray-700'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-white text-sm truncate">
                      {bp.label}
                    </div>
                    <div className="text-xs text-gray-400 mt-1 truncate">
                      {bp.file_path}
                    </div>
                  </div>
                  <span className="shrink-0 text-xs px-2 py-0.5 rounded bg-gray-700 text-gray-300 font-medium">
                    {routeCount}
                  </span>
                </div>
              </button>
            );
          })}
          {blueprints.length === 0 && (
            <div className="text-center py-8 text-gray-500">
              <p className="text-sm">No blueprints found</p>
            </div>
          )}
        </div>
      </div>

      {/* Right panel: Blueprint subgraph */}
      <div className="flex-1 overflow-y-auto p-6">
        {!subgraph ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center text-gray-500">
              <p className="text-4xl mb-4">📦</p>
              <p className="text-lg">Select a blueprint from the left to explore its subgraph</p>
            </div>
          </div>
        ) : (
          <div className="max-w-5xl mx-auto space-y-6">
            {/* Header */}
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-white mb-2 flex items-center gap-3">
                <span
                  className="w-4 h-4 rounded-full"
                  style={{ backgroundColor: NODE_COLORS.blueprint }}
                />
                {subgraph.blueprint.label}
              </h2>
              <div className="text-sm text-gray-400 space-y-1">
                <p>{subgraph.blueprint.file_path}:{subgraph.blueprint.line_number}</p>
                <p>
                  {subgraph.routes.length} route{subgraph.routes.length !== 1 ? 's' : ''},{' '}
                  {subgraph.actions.length} action{subgraph.actions.length !== 1 ? 's' : ''},{' '}
                  {subgraph.services.length} service{subgraph.services.length !== 1 ? 's' : ''},{' '}
                  {subgraph.models.length} model{subgraph.models.length !== 1 ? 's' : ''}
                </p>
              </div>
            </div>

            {/* Sections */}
            <div className="space-y-4">
              {renderSection('Routes', 'routes', subgraph.routes, 2)}
              {renderSection('Actions', 'actions', subgraph.actions, 2)}
              {renderSection('Services', 'services', subgraph.services, 2)}
              {renderSection('Models', 'models', subgraph.models, 3)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
