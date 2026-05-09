import { useState, useCallback } from 'react';
import { NODE_COLORS } from '../utils/cytoscapeStyles';
import type { Node } from '../types/graph';

interface SearchViewProps {
  onNodeSelect: (node: Node) => void;
  selectedNodeId?: string | null;
}

const PREDICATE_EXAMPLES = [
  { label: 'type=route', desc: 'All routes' },
  { label: 'type=service complexity>20', desc: 'Fat services' },
  { label: 'model=User', desc: 'Nodes using User model' },
  { label: 'type=action blueprint=auth', desc: 'Actions in auth blueprint' },
  { label: 'complexity>30', desc: 'High-complexity nodes' },
];

export function SearchView({ onNodeSelect, selectedNodeId }: SearchViewProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Node[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [lastQuery, setLastQuery] = useState('');

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim()) { setResults(null); return; }
    setLoading(true);
    setLastQuery(q);
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(q)}&limit=200`);
      const data = await res.json();
      setResults(data.nodes || []);
    } catch (e) {
      console.error('Search error', e);
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') doSearch(query);
  };

  return (
    <div className="h-full overflow-y-auto bg-white dark:bg-gray-900 p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2 flex items-center gap-2">
            <span>🔎</span> Search
          </h2>
          <p className="text-gray-600 dark:text-gray-400 text-sm">
            Free-text search or use predicates: <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">type=</code>{' '}
            <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">model=</code>{' '}
            <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">blueprint=</code>{' '}
            <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">complexity&gt;</code>{' '}
            <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">complexity&lt;</code>
          </p>
        </div>

        {/* Search bar */}
        <div className="flex gap-3">
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder='e.g. "type=service complexity>20" or "contractor"'
            className="flex-1 px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={() => doSearch(query)}
            disabled={loading}
            className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg font-medium transition-colors"
          >
            {loading ? '…' : 'Search'}
          </button>
        </div>

        {/* Example predicates */}
        {!results && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-2">Examples</p>
            <div className="flex flex-wrap gap-2">
              {PREDICATE_EXAMPLES.map(ex => (
                <button
                  key={ex.label}
                  onClick={() => { setQuery(ex.label); doSearch(ex.label); }}
                  className="px-3 py-1.5 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg text-sm text-gray-700 dark:text-gray-300 transition-colors"
                  title={ex.desc}
                >
                  {ex.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Results */}
        {results !== null && (
          <div>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">
              {results.length} result{results.length !== 1 ? 's' : ''} for <strong>"{lastQuery}"</strong>
            </p>
            {results.length === 0 ? (
              <div className="text-center py-12 text-gray-400 dark:text-gray-500">
                <p className="text-3xl mb-3">🤷</p>
                <p>No nodes matched your query.</p>
              </div>
            ) : (
              <div className="space-y-1.5">
                {results.map(node => {
                  const isSelected = node.id === selectedNodeId;
                  return (
                    <button
                      key={node.id}
                      onClick={() => onNodeSelect(node)}
                      className={`w-full text-left flex items-start gap-3 p-3 rounded-lg border transition-all ${
                        isSelected
                          ? 'bg-blue-50 dark:bg-blue-900/20 border-blue-400 dark:border-blue-600'
                          : 'bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-750'
                      }`}
                    >
                      <span
                        className="mt-0.5 w-3 h-3 rounded-full shrink-0"
                        style={{ backgroundColor: NODE_COLORS[node.type] || '#888' }}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="font-medium text-gray-900 dark:text-white truncate">
                          {node.label}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400 truncate mt-0.5">
                          {node.file_path}{node.line_number ? `:${node.line_number}` : ''}
                        </div>
                      </div>
                      <div className="shrink-0 flex flex-col items-end gap-1">
                        <span className="text-xs px-2 py-0.5 rounded font-medium text-white" style={{ backgroundColor: NODE_COLORS[node.type] || '#888' }}>
                          {node.type}
                        </span>
                        {node.metadata?.complexity !== undefined && (
                          <span className="text-xs text-gray-500 dark:text-gray-400 font-mono">cx {node.metadata.complexity}</span>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
