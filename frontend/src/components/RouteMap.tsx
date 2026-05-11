import { useMemo, useRef, useEffect } from 'react';
import type { Graph, Node } from '../types/graph';

interface RouteMapProps {
  graph: Graph;
  onRouteSelect: (routeNode: Node) => void;
  selectedNodeId?: string | null;
}

export function RouteMap({ graph, onRouteSelect, selectedNodeId }: RouteMapProps) {
  const selectedRouteRef = useRef<HTMLButtonElement>(null);

  const routesByBlueprint = useMemo(() => {
    const routes = graph.nodes.filter(n => n.type === 'route');
    const grouped = new Map<string, Node[]>();
    
    routes.forEach(route => {
      const blueprint = route.metadata.blueprint || 'No Blueprint';
      if (!grouped.has(blueprint)) {
        grouped.set(blueprint, []);
      }
      grouped.get(blueprint)!.push(route);
    });
    
    // Sort routes within each blueprint
    grouped.forEach(routes => {
      routes.sort((a, b) => a.label.localeCompare(b.label));
    });
    
    return grouped;
  }, [graph]);

  // Auto-scroll to selected route
  useEffect(() => {
    if (selectedNodeId && selectedRouteRef.current) {
      selectedRouteRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [selectedNodeId]);

  const getMethodBadgeColor = (method: string) => {
    switch (method.toUpperCase()) {
      case 'GET': return 'bg-green-500 text-white';
      case 'POST': return 'bg-blue-500 text-white';
      case 'PUT': return 'bg-yellow-500 text-white';
      case 'DELETE': return 'bg-red-500 text-white';
      case 'PATCH': return 'bg-orange-500 text-white';
      default: return 'bg-gray-500 text-white';
    }
  };

  return (
    <div className="h-full overflow-y-auto bg-white dark:bg-gray-900 p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Route Map</h2>
          <p className="text-gray-600 dark:text-gray-400">
            All routes grouped by blueprint. Click a route to view it in the graph.
          </p>
        </div>

        {Array.from(routesByBlueprint.entries()).map(([blueprint, routes]) => (
          <div key={blueprint} className="bg-gray-50 dark:bg-gray-800 rounded-lg overflow-hidden">
            <div className="bg-teal-600 px-4 py-3">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
                </svg>
                {blueprint}
              </h3>
              <p className="text-teal-100 text-sm mt-1">{routes.length} route{routes.length !== 1 ? 's' : ''}</p>
            </div>

            <div className="divide-y divide-gray-200 dark:divide-gray-700">
              {routes.map(route => {
                const isSelected = route.id === selectedNodeId;
                return (
                  <button
                    key={route.id}
                    ref={isSelected ? selectedRouteRef : null}
                    onClick={() => onRouteSelect(route)}
                    className={`w-full px-4 py-3 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-left ${
                      isSelected ? 'border-l-4 border-blue-500 bg-blue-50 dark:bg-blue-900/20' : ''
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex gap-1">
                        {route.metadata.methods?.map(method => (
                          <span
                            key={method}
                            className={`px-2 py-1 rounded text-xs font-bold ${getMethodBadgeColor(method)}`}
                          >
                            {method}
                          </span>
                        ))}
                      </div>
                      <div className="flex-1">
                        <p className="font-mono text-sm text-gray-900 dark:text-white">{route.label}</p>
                        <div className="flex items-center gap-2 mt-1">
                          {route.metadata.view_function && (
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                              → {route.metadata.view_function}
                            </p>
                          )}
                          {route.metadata.auth_required && (
                            <span
                              className="inline-flex items-center gap-1 text-xs text-amber-700 dark:text-amber-400 font-medium"
                              title={
                                route.metadata.decorators && route.metadata.decorators.length > 0
                                  ? route.metadata.decorators.map(d => `@${d}`).join(', ')
                                  : 'auth required'
                              }
                            >
                              <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
                              </svg>
                              auth
                            </span>
                          )}
                          {!route.metadata.auth_required && route.metadata.decorators && route.metadata.decorators.length > 0 && (
                            <span
                              className="inline-flex items-center gap-1 text-xs text-gray-400 dark:text-gray-500 font-mono"
                              title={route.metadata.decorators.map(d => `@${d}`).join(', ')}
                            >
                              @{route.metadata.decorators[0]}
                              {route.metadata.decorators.length > 1 && ` +${route.metadata.decorators.length - 1}`}
                            </span>
                          )}
                        </div>
                      </div>
                      <svg className="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        ))}

        {routesByBlueprint.size === 0 && (
          <div className="text-center py-12">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p className="mt-4 text-gray-600 dark:text-gray-400">No routes found in the graph.</p>
          </div>
        )}
      </div>
    </div>
  );
}
