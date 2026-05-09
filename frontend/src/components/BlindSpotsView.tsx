import { useState, useEffect } from 'react';
import type { Node } from '../types/graph';

interface BlindSpotsResponse {
  count: number;
  nodes: Node[];
}

interface BlindSpotsViewProps {
  onNodeSelect: (node: Node) => void;
  selectedNodeId?: string | null;
}

const TYPE_BADGE: Record<string, string> = {
  service: 'bg-purple-200 dark:bg-purple-800 text-purple-900 dark:text-purple-100',
  action: 'bg-blue-200 dark:bg-blue-800 text-blue-900 dark:text-blue-100',
  task: 'bg-orange-200 dark:bg-orange-800 text-orange-900 dark:text-orange-100',
};

export function BlindSpotsView({ onNodeSelect, selectedNodeId }: BlindSpotsViewProps) {
  const [data, setData] = useState<BlindSpotsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    fetch('/api/analysis/blind-spots')
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-white dark:bg-gray-900">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-4 border-red-500 mx-auto"></div>
          <p className="mt-4 text-gray-600 dark:text-gray-400">Analyzing blind spots…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center bg-white dark:bg-gray-900">
        <p className="text-red-500">Error: {error}</p>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="h-full overflow-y-auto bg-white dark:bg-gray-900 p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2 flex items-center gap-2">
            <span>🔍</span> Model Linkage Blind Spots
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            <strong>{data.count}</strong> node{data.count !== 1 ? 's' : ''} detected making DB calls but with <strong>no resolved model edge</strong>.
            The query tracer found database operations but couldn't statically determine which model was used.
            These represent scanner coverage gaps — review manually for architecture accuracy.
          </p>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap gap-4 p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg text-sm text-amber-900 dark:text-amber-200">
          <span className="font-semibold">Why this happens:</span>
          <span>Dynamic model lookups · String-based <code>db.session.query('ModelName')</code> · ORM aliasing · Generic repositories</span>
        </div>

        {/* Node list */}
        {data.nodes.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-4xl mb-4">✅</p>
            <p className="text-lg font-semibold text-gray-900 dark:text-white">No blind spots detected</p>
            <p className="text-gray-500 dark:text-gray-400 mt-1">All DB-calling nodes have at least one resolved model edge.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {data.nodes.map(node => {
              const isSelected = node.id === selectedNodeId;
              const dbOps = node.metadata?.db_op_count ?? 0;
              return (
                <button
                  key={node.id}
                  onClick={() => onNodeSelect(node)}
                  className={`w-full text-left flex items-start gap-3 p-3 rounded-lg border transition-all ${
                    isSelected
                      ? 'bg-red-50 dark:bg-red-900/20 border-red-400 dark:border-red-600'
                      : 'bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-750'
                  }`}
                >
                  <span className={`mt-0.5 px-2 py-0.5 rounded text-xs font-mono font-bold shrink-0 ${TYPE_BADGE[node.type] || 'bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-200'}`}>
                    {node.type}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-gray-900 dark:text-white truncate">
                      {node.label}
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 truncate mt-0.5">
                      {node.file_path}{node.line_number ? `:${node.line_number}` : ''}
                    </div>
                  </div>
                  <div className="shrink-0 flex flex-col items-end gap-1">
                    <span className="text-xs font-mono font-semibold text-red-600 dark:text-red-400">
                      {dbOps} DB op{dbOps !== 1 ? 's' : ''}
                    </span>
                    {node.metadata?.complexity !== undefined && (
                      <span className="text-xs text-gray-500 dark:text-gray-400 font-mono">
                        cx {node.metadata.complexity}
                      </span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
