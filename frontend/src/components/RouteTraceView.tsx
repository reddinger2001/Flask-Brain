import { useState, useMemo } from 'react';
import { NODE_COLORS } from '../utils/cytoscapeStyles';
import type { Node, Graph } from '../types/graph';

interface RouteTraceViewProps {
  graph: Graph;
  onNodeSelect: (node: Node | null) => void;
  selectedNodeId: string | null;
}

interface TraceChain {
  route: Node;
  actions: Node[];
  services: Node[];
  models: Node[];
}

const HTTP_METHOD_COLORS: Record<string, string> = {
  GET: 'bg-green-600',
  POST: 'bg-blue-600',
  PUT: 'bg-yellow-600',
  DELETE: 'bg-red-600',
  PATCH: 'bg-orange-600',
};

export function RouteTraceView({ graph, onNodeSelect, selectedNodeId }: RouteTraceViewProps) {
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Extract all route nodes, sorted alphabetically
  const routes = useMemo(() => {
    return graph.nodes
      .filter(n => n.type === 'route')
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [graph.nodes]);

  // Filter routes by search query
  const filteredRoutes = useMemo(() => {
    if (!searchQuery.trim()) return routes;
    const q = searchQuery.toLowerCase();
    return routes.filter(r => 
      r.label.toLowerCase().includes(q) || 
      r.metadata.blueprint?.toLowerCase().includes(q)
    );
  }, [routes, searchQuery]);

  // Compute the execution chain for the selected route
  const traceChain = useMemo((): TraceChain | null => {
    if (!selectedRouteId) return null;

    const route = graph.nodes.find(n => n.id === selectedRouteId);
    if (!route) return null;

    // Find actions called by this route
    const actionIds = new Set(
      graph.edges
        .filter(e => e.source === selectedRouteId && e.type === 'calls')
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

    // Find models used by route, actions, or services
    const modelIds = new Set(
      graph.edges
        .filter(e => 
          e.type === 'uses_model' && 
          (e.source === selectedRouteId || actionIds.has(e.source) || serviceIds.has(e.source))
        )
        .map(e => e.target)
    );
    const models = graph.nodes.filter(n => modelIds.has(n.id) && n.type === 'model');

    return { route, actions, services, models };
  }, [selectedRouteId, graph]);

  const handleRouteClick = (route: Node) => {
    setSelectedRouteId(route.id);
    onNodeSelect(route);
  };

  const renderNodeCard = (node: Node, large = false) => {
    const isSelected = node.id === selectedNodeId;
    return (
      <button
        key={node.id}
        onClick={() => onNodeSelect(node)}
        className={`text-left p-4 rounded-lg border transition-all ${
          large ? 'w-full' : 'w-full'
        } ${
          isSelected
            ? 'ring-2 ring-blue-500 bg-gray-700 border-gray-600'
            : 'bg-gray-700 hover:bg-gray-600 border-gray-600'
        }`}
      >
        <div className="flex items-start gap-3">
          <span
            className="mt-1 w-4 h-4 rounded-full shrink-0"
            style={{ backgroundColor: NODE_COLORS[node.type] || '#888' }}
          />
          <div className="min-w-0 flex-1">
            <div className={`font-medium text-white ${large ? 'text-lg' : ''}`}>
              {node.label}
            </div>
            <div className="text-xs text-gray-400 mt-1">
              {node.file_path}:{node.line_number}
            </div>
          </div>
        </div>
      </button>
    );
  };

  const renderArrow = () => (
    <div className="flex justify-center py-2">
      <svg width="24" height="24" viewBox="0 0 24 24" className="text-gray-500">
        <path
          fill="currentColor"
          d="M12 4l-1.41 1.41L16.17 11H4v2h12.17l-5.58 5.59L12 20l8-8z"
          transform="rotate(90 12 12)"
        />
      </svg>
    </div>
  );

  return (
    <div className="h-full flex bg-gray-900">
      {/* Left panel: Route list */}
      <div className="w-80 bg-gray-800 border-r border-gray-700 flex flex-col">
        <div className="p-4 border-b border-gray-700">
          <h3 className="text-lg font-bold text-white mb-3">Routes</h3>
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="Search routes..."
            className="w-full px-3 py-2 rounded-lg border border-gray-600 bg-gray-700 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
          />
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {filteredRoutes.map(route => {
            const isActive = route.id === selectedRouteId;
            const methods = route.metadata.methods || [];
            const blueprint = route.metadata.blueprint || 'unknown';

            return (
              <button
                key={route.id}
                onClick={() => handleRouteClick(route)}
                className={`w-full text-left p-3 rounded-lg border transition-all ${
                  isActive
                    ? 'bg-gray-700 border-blue-500'
                    : 'bg-gray-750 border-gray-700 hover:bg-gray-700'
                }`}
              >
                <div className="flex items-start gap-2 mb-2">
                  {methods.map(method => (
                    <span
                      key={method}
                      className={`text-xs px-2 py-0.5 rounded font-medium text-white ${
                        HTTP_METHOD_COLORS[method] || 'bg-gray-600'
                      }`}
                    >
                      {method}
                    </span>
                  ))}
                </div>
                <div className="font-medium text-white text-sm truncate">
                  {route.label}
                </div>
                <div className="text-xs text-gray-400 mt-1">
                  {blueprint}
                </div>
              </button>
            );
          })}
          {filteredRoutes.length === 0 && (
            <div className="text-center py-8 text-gray-500">
              <p className="text-sm">No routes found</p>
            </div>
          )}
        </div>
      </div>

      {/* Right panel: Execution trace */}
      <div className="flex-1 overflow-y-auto p-6">
        {!traceChain ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center text-gray-500">
              <p className="text-4xl mb-4">🔍</p>
              <p className="text-lg">Select a route from the left to trace its execution path</p>
            </div>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto space-y-4">
            {/* Header */}
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-white mb-2">Execution Trace</h2>
              <p className="text-gray-400 text-sm">
                Full call chain from route to models
              </p>
            </div>

            {/* Route */}
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">
                Route
              </div>
              {renderNodeCard(traceChain.route, true)}
            </div>

            {renderArrow()}

            {/* Actions */}
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">
                Actions <span className="text-gray-500">({traceChain.actions.length})</span>
              </div>
              {traceChain.actions.length === 0 ? (
                <div className="text-center py-6 text-gray-500 bg-gray-800 rounded-lg border border-gray-700">
                  <p className="text-sm">No action wired</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {traceChain.actions.map(node => renderNodeCard(node))}
                </div>
              )}
            </div>

            {traceChain.actions.length > 0 && (
              <>
                {renderArrow()}

                {/* Services */}
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">
                    Services <span className="text-gray-500">({traceChain.services.length})</span>
                  </div>
                  {traceChain.services.length === 0 ? (
                    <div className="text-center py-6 text-gray-500 bg-gray-800 rounded-lg border border-gray-700">
                      <p className="text-sm">No services called</p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 gap-2">
                      {traceChain.services.map(node => renderNodeCard(node))}
                    </div>
                  )}
                </div>

                {(traceChain.services.length > 0 || traceChain.models.length > 0) && renderArrow()}

                {/* Models */}
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">
                    Models <span className="text-gray-500">({traceChain.models.length})</span>
                  </div>
                  {traceChain.models.length === 0 ? (
                    <div className="text-center py-6 text-gray-500 bg-gray-800 rounded-lg border border-gray-700">
                      <p className="text-sm">No models touched</p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 gap-2">
                      {traceChain.models.map(node => renderNodeCard(node))}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
