import { useState, useEffect } from 'react';
import type { Node } from '../types/graph';

interface DeadWeightResponse {
  count: number;
  nodes: Node[];
}

interface DeadWeightViewProps {
  onNodeSelect: (node: Node) => void;
  selectedNodeId?: string | null;
}

const TYPE_LABELS: Record<string, string> = {
  service: 'Services',
  action: 'Actions (View Functions)',
  task: 'Celery Tasks',
};

const TYPE_COLORS: Record<string, string> = {
  service: 'bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-200 border-purple-300 dark:border-purple-700',
  action: 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200 border-blue-300 dark:border-blue-700',
  task: 'bg-orange-100 dark:bg-orange-900/30 text-orange-800 dark:text-orange-200 border-orange-300 dark:border-orange-700',
};

const TYPE_BADGE: Record<string, string> = {
  service: 'bg-purple-200 dark:bg-purple-800 text-purple-900 dark:text-purple-100',
  action: 'bg-blue-200 dark:bg-blue-800 text-blue-900 dark:text-blue-100',
  task: 'bg-orange-200 dark:bg-orange-800 text-orange-900 dark:text-orange-100',
};

export function DeadWeightView({ onNodeSelect, selectedNodeId }: DeadWeightViewProps) {
  const [data, setData] = useState<DeadWeightResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    setLoading(true);
    fetch('/api/analysis/dead-weight')
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-white dark:bg-gray-900">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-4 border-yellow-500 mx-auto"></div>
          <p className="mt-4 text-gray-600 dark:text-gray-400">Analyzing dead weight…</p>
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

  // Group by type
  const grouped: Record<string, Node[]> = {};
  for (const node of data.nodes) {
    if (!grouped[node.type]) grouped[node.type] = [];
    grouped[node.type].push(node);
  }

  const filteredNodes = filter === 'all' ? data.nodes : (grouped[filter] || []);
  const typeOrder = ['service', 'action', 'task'];

  return (
    <div className="h-full overflow-y-auto bg-white dark:bg-gray-900 p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2 flex items-center gap-2">
            <span>💀</span> Dead Weight Detector
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            {data.count} node{data.count !== 1 ? 's' : ''} with <strong>no incoming edges</strong> — nothing in the graph calls them.
            These may be dead code, test helpers, or migration scripts.
          </p>
        </div>

        {/* Summary badges */}
        <div className="flex flex-wrap gap-3">
          {typeOrder.filter(t => grouped[t]?.length).map(type => (
            <button
              key={type}
              onClick={() => setFilter(filter === type ? 'all' : type)}
              className={`px-4 py-2 rounded-full text-sm font-medium border transition-all ${TYPE_COLORS[type]} ${filter === type ? 'ring-2 ring-offset-2 ring-yellow-500' : ''}`}
            >
              {TYPE_LABELS[type] || type}: {grouped[type].length}
            </button>
          ))}
          {filter !== 'all' && (
            <button
              onClick={() => setFilter('all')}
              className="px-4 py-2 rounded-full text-sm font-medium bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600"
            >
              Show all
            </button>
          )}
        </div>

        {/* Node list */}
        {filteredNodes.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-4xl mb-4">✅</p>
            <p className="text-lg font-semibold text-gray-900 dark:text-white">No dead weight detected</p>
            <p className="text-gray-500 dark:text-gray-400 mt-1">Every node is reachable from at least one caller.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {filteredNodes.map(node => {
              const isSelected = node.id === selectedNodeId;
              return (
                <button
                  key={node.id}
                  onClick={() => onNodeSelect(node)}
                  className={`w-full text-left flex items-start gap-3 p-3 rounded-lg border transition-all ${
                    isSelected
                      ? 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-400 dark:border-yellow-600'
                      : 'bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-750'
                  }`}
                >
                  <span className={`mt-0.5 px-2 py-0.5 rounded text-xs font-mono font-bold shrink-0 ${TYPE_BADGE[node.type] || 'bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-200'}`}>
                    {node.type}
                  </span>
                  <div className="min-w-0">
                    <div className="font-medium text-gray-900 dark:text-white truncate">
                      {node.label}
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 truncate mt-0.5">
                      {node.file_path}{node.line_number ? `:${node.line_number}` : ''}
                    </div>
                  </div>
                  {node.metadata?.complexity !== undefined && (
                    <span className="ml-auto shrink-0 text-xs text-gray-500 dark:text-gray-400 font-mono">
                      cx {node.metadata.complexity}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
