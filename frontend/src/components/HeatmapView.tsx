import { useMemo, useRef, useEffect } from 'react';
import { COMPLEXITY_COLORS } from '../utils/cytoscapeStyles';
import type { Graph, Node } from '../types/graph';

interface HeatmapViewProps {
  graph: Graph;
  onNodeSelect: (node: Node) => void;
  selectedNodeId?: string | null;
}

export function HeatmapView({ graph, onNodeSelect, selectedNodeId }: HeatmapViewProps) {
  const selectedCardRef = useRef<HTMLButtonElement>(null);

  const functionsWithComplexity = useMemo(() => {
    return graph.nodes
      .filter(n => (n.type === 'action' || n.type === 'service') && n.metadata.complexity !== undefined)
      .sort((a, b) => (b.metadata.complexity || 0) - (a.metadata.complexity || 0));
  }, [graph]);

  const stats = useMemo(() => {
    const tiers = { low: 0, moderate: 0, high: 0, critical: 0 };
    functionsWithComplexity.forEach(node => {
      const tier = node.metadata.complexity_tier;
      if (tier) tiers[tier]++;
    });
    return tiers;
  }, [functionsWithComplexity]);

  // Auto-scroll to selected card
  useEffect(() => {
    if (selectedNodeId && selectedCardRef.current) {
      selectedCardRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [selectedNodeId]);

  if (functionsWithComplexity.length === 0) {
    return (
      <div className="h-full flex items-center justify-center bg-white dark:bg-gray-900">
        <div className="text-center">
          <svg className="mx-auto h-16 w-16 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <p className="mt-4 text-lg text-gray-600 dark:text-gray-400">No complexity data available.</p>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-500">
            Complexity metrics will appear here once functions are analyzed.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto bg-white dark:bg-gray-900 p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Complexity Heatmap</h2>
          <p className="text-gray-600 dark:text-gray-400">
            All functions and services colored by cyclomatic complexity. Click to view in graph.
          </p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4">
          <div className="bg-green-50 dark:bg-green-900/20 border-2 border-green-500 rounded-lg p-4">
            <div className="text-3xl font-bold text-green-700 dark:text-green-400">{stats.low}</div>
            <div className="text-sm font-semibold text-green-600 dark:text-green-300 mt-1">Low (1-5)</div>
          </div>
          <div className="bg-yellow-50 dark:bg-yellow-900/20 border-2 border-yellow-500 rounded-lg p-4">
            <div className="text-3xl font-bold text-yellow-700 dark:text-yellow-400">{stats.moderate}</div>
            <div className="text-sm font-semibold text-yellow-600 dark:text-yellow-300 mt-1">Moderate (6-10)</div>
          </div>
          <div className="bg-orange-50 dark:bg-orange-900/20 border-2 border-orange-500 rounded-lg p-4">
            <div className="text-3xl font-bold text-orange-700 dark:text-orange-400">{stats.high}</div>
            <div className="text-sm font-semibold text-orange-600 dark:text-orange-300 mt-1">High (11-20)</div>
          </div>
          <div className="bg-red-50 dark:bg-red-900/20 border-2 border-red-500 rounded-lg p-4">
            <div className="text-3xl font-bold text-red-700 dark:text-red-400">{stats.critical}</div>
            <div className="text-sm font-semibold text-red-600 dark:text-red-300 mt-1">Critical (21+)</div>
          </div>
        </div>

        {/* Function Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {functionsWithComplexity.map(node => {
            const tier = node.metadata.complexity_tier || 'low';
            const isSelected = node.id === selectedNodeId;
            const bgColor = {
              low: 'bg-green-50 dark:bg-green-900/20 border-green-500',
              moderate: 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-500',
              high: 'bg-orange-50 dark:bg-orange-900/20 border-orange-500',
              critical: 'bg-red-50 dark:bg-red-900/20 border-red-500',
            }[tier];

            return (
              <button
                key={node.id}
                ref={isSelected ? selectedCardRef : null}
                onClick={() => onNodeSelect(node)}
                className={`${bgColor} border-2 rounded-lg p-4 text-left hover:shadow-lg transition-all ${
                  isSelected ? 'ring-2 ring-blue-500 scale-[1.02]' : ''
                }`}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-900 dark:text-white break-words">
                      {node.label}
                    </h3>
                    <p className="text-xs text-gray-600 dark:text-gray-400 mt-1 font-mono">
                      {node.file_path}
                    </p>
                  </div>
                  <span
                    className="ml-2 px-2 py-1 rounded text-xs font-bold text-white flex-shrink-0"
                    style={{ backgroundColor: COMPLEXITY_COLORS[tier] }}
                  >
                    {node.metadata.complexity}
                  </span>
                </div>

                <div className="flex items-center gap-4 text-xs text-gray-600 dark:text-gray-400 mt-3">
                  <div className="flex items-center gap-1">
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                    </svg>
                    <span>{node.metadata.line_count || 0} lines</span>
                  </div>
                  
                  {node.type === 'service' && (
                    <div className="flex items-center gap-1">
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                      </svg>
                      <span>Service</span>
                    </div>
                  )}
                  
                  {node.type === 'action' && (
                    <div className="flex items-center gap-1">
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                      <span>Action</span>
                    </div>
                  )}
                </div>

                {node.metadata.is_fat && (
                  <div className="mt-3 flex items-center gap-1 text-xs font-semibold text-yellow-700 dark:text-yellow-300">
                    <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                    Fat Service
                  </div>
                )}

                {node.metadata.db_operations && node.metadata.db_operations.length > 0 && (
                  <div className="mt-3 flex items-center gap-1 text-xs text-gray-600 dark:text-gray-400">
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                    </svg>
                    <span>{node.metadata.db_operations.length} DB op{node.metadata.db_operations.length !== 1 ? 's' : ''}</span>
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
