import { useState, useCallback, useEffect } from 'react';
import type { Node } from '../types/graph';

interface PropertyTraceViewProps {
  onNodeSelect: (node: Node) => void;
  selectedNodeId?: string | null;
}

interface PropertyDefinition {
  kind: string;
  file: string;
  line: number;
  class: string;
}

interface PropertyUsage {
  file: string;
  line: number;
  context: string;
}

interface PropertyResult {
  node_id: string;
  class_name: string;
  prop_name: string;
  file_path: string;
  has_getter: boolean;
  has_setter: boolean;
  has_deleter: boolean;
  orphaned_getter: boolean;
  orphaned_setter: boolean;
  definitions: PropertyDefinition[];
  reads: PropertyUsage[];
  writes: PropertyUsage[];
  readers: string[];
  writers: string[];
}

export function PropertyTraceView({ onNodeSelect }: PropertyTraceViewProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<PropertyResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [lastQuery, setLastQuery] = useState('');
  const [totalProperties, setTotalProperties] = useState<number | null>(null);

  // On mount, check how many property nodes are in the current scan
  useEffect(() => {
    fetch('/api/properties/all')
      .then(r => r.json())
      .then(d => setTotalProperties(d.count ?? 0))
      .catch(() => setTotalProperties(0));
  }, []);

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim()) { setResults(null); return; }
    setLoading(true);
    setLastQuery(q);
    try {
      const res = await fetch(`/api/trace/property?name=${encodeURIComponent(q)}`);
      const data = await res.json();
      setResults(data.results || []);
    } catch (e) {
      console.error('Property trace error', e);
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') doSearch(query);
  };

  const handleNodeClick = (nodeId: string) => {
    // Create a minimal Node object for selection
    const node: Node = {
      id: nodeId,
      type: 'property',
      label: nodeId.split('::')[1] || nodeId,
      file_path: '',
      line_number: 0,
      metadata: {},
    };
    onNodeSelect(node);
  };

  return (
    <div className="h-full overflow-y-auto bg-white dark:bg-gray-900 p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2 flex items-center gap-2">
            <span>🔍</span> Property Trace
          </h2>
          <p className="text-gray-600 dark:text-gray-400 text-sm">
            Search for a variable or property name to trace it across the codebase
            {totalProperties !== null && totalProperties > 0 && (
              <span className="ml-2 text-cyan-600 dark:text-cyan-400 font-medium">
                — {totalProperties.toLocaleString()} properties indexed
              </span>
            )}
          </p>
        </div>

        {/* Rescan warning — shown when no property nodes exist in the current graph */}
        {totalProperties === 0 && (
          <div className="flex items-start gap-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-300 dark:border-yellow-700 rounded-lg p-4">
            <span className="text-2xl">⚠️</span>
            <div>
              <p className="font-semibold text-yellow-800 dark:text-yellow-300">No property data in current scan</p>
              <p className="text-sm text-yellow-700 dark:text-yellow-400 mt-1">
                Your graph was scanned before the Property Trace feature was added.
                Re-run <code className="bg-yellow-100 dark:bg-yellow-900 px-1 rounded">flask-brain scan &lt;path&gt;</code> to index properties.
              </p>
            </div>
          </div>
        )}

        {/* Search bar */}
        <div className="flex gap-3">
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder='e.g. "portal_link_id" or "status"'
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

        {/* Empty state */}
        {!results && (
          <div className="text-center py-12 text-gray-400 dark:text-gray-500">
            <p className="text-3xl mb-3">🔍</p>
            <p>Search for a variable or property name to trace it across the codebase</p>
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
                <p>No properties matched your query.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {results.map(prop => (
                  <div
                    key={prop.node_id}
                    className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4"
                  >
                    {/* Header */}
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                          {prop.class_name}.{prop.prop_name}
                        </h3>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                          {prop.file_path}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <span
                          className={`text-xs px-2 py-1 rounded font-medium ${
                            prop.has_getter
                              ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                              : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
                          }`}
                        >
                          {prop.has_getter ? '✅' : '❌'} getter
                        </span>
                        <span
                          className={`text-xs px-2 py-1 rounded font-medium ${
                            prop.has_setter
                              ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                              : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
                          }`}
                        >
                          {prop.has_setter ? '✅' : '❌'} setter
                        </span>
                        {prop.has_deleter && (
                          <span className="text-xs px-2 py-1 rounded font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400">
                            ✅ deleter
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Orphaned warning */}
                    {(prop.orphaned_getter || prop.orphaned_setter) && (
                      <div className="mb-3 p-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded text-sm text-red-700 dark:text-red-400">
                        ⚠️ {prop.orphaned_getter ? 'Orphaned getter — no setter defined' : 'Orphaned setter — no getter defined'}
                      </div>
                    )}

                    {/* Definitions */}
                    {prop.definitions.length > 0 && (
                      <div className="mb-3">
                        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-1">
                          Defined in:
                        </p>
                        <div className="space-y-1">
                          {prop.definitions.map((def, idx) => (
                            <div key={idx} className="text-sm text-gray-700 dark:text-gray-300 flex items-center gap-2">
                              <span className="px-2 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs font-mono">
                                {def.kind}
                              </span>
                              <span className="font-medium">{def.class}</span>
                              <span className="text-gray-500 dark:text-gray-400">
                                {def.file}:{def.line}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Read by */}
                    {prop.readers.length > 0 && (
                      <div className="mb-3">
                        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-1">
                          Read by ({prop.readers.length}):
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {prop.readers.map((reader, idx) => (
                            <button
                              key={idx}
                              onClick={() => handleNodeClick(`action::${reader}`)}
                              className="px-2 py-1 bg-blue-100 dark:bg-blue-900/30 hover:bg-blue-200 dark:hover:bg-blue-900/50 text-blue-700 dark:text-blue-400 rounded text-xs font-medium transition-colors"
                            >
                              {reader}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Written by */}
                    {prop.writers.length > 0 && (
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-1">
                          Written by ({prop.writers.length}):
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {prop.writers.map((writer, idx) => (
                            <button
                              key={idx}
                              onClick={() => handleNodeClick(`action::${writer}`)}
                              className="px-2 py-1 bg-purple-100 dark:bg-purple-900/30 hover:bg-purple-200 dark:hover:bg-purple-900/50 text-purple-700 dark:text-purple-400 rounded text-xs font-medium transition-colors"
                            >
                              {writer}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Detailed reads/writes */}
                    {(prop.reads.length > 0 || prop.writes.length > 0) && (
                      <details className="mt-3">
                        <summary className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 cursor-pointer hover:text-gray-700 dark:hover:text-gray-300">
                          Show all usages ({prop.reads.length + prop.writes.length})
                        </summary>
                        <div className="mt-2 space-y-1 pl-4">
                          {prop.reads.map((read, idx) => (
                            <div key={`read-${idx}`} className="text-xs text-gray-600 dark:text-gray-400">
                              <span className="text-blue-600 dark:text-blue-400 font-medium">READ</span>{' '}
                              {read.context} — {read.file}:{read.line}
                            </div>
                          ))}
                          {prop.writes.map((write, idx) => (
                            <div key={`write-${idx}`} className="text-xs text-gray-600 dark:text-gray-400">
                              <span className="text-purple-600 dark:text-purple-400 font-medium">WRITE</span>{' '}
                              {write.context} — {write.file}:{write.line}
                            </div>
                          ))}
                        </div>
                      </details>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
