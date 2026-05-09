import { useState, useEffect } from 'react';
import type { Node } from '../types/graph';

// ── API types ─────────────────────────────────────────────────────────────────

interface Snapshot {
  id: string;
  created_at: string;
  label: string | null;
  node_count: number;
  edge_count: number;
}

interface NodeChange {
  node_id: string;
  change_type: 'added' | 'removed' | 'modified';
  old_node: Partial<Node> | null;
  new_node: Partial<Node> | null;
  changes: Record<string, { old: unknown; new: unknown }>;
}

interface EdgeChange {
  source: string;
  target: string;
  edge_type: string;
  change_type: 'added' | 'removed';
  old_edge: object | null;
  new_edge: object | null;
}

interface DiffSummary {
  nodes_added: number;
  nodes_removed: number;
  nodes_modified: number;
  edges_added: number;
  edges_removed: number;
}

interface DiffResponse {
  baseline_id: string;
  current_id: string;
  summary: DiffSummary;
  node_changes: NodeChange[];
  edge_changes: EdgeChange[];
}

interface DiffViewProps {
  onNodeSelect: (node: Node) => void;
  selectedNodeId?: string | null;
}

// ── Constants ──────────────────────────────────────────────────────────────────

const CHANGE_ICONS: Record<string, string> = {
  added: '+',
  removed: '−',
  modified: '~',
};

const CHANGE_COLORS: Record<string, string> = {
  added: 'text-green-600 dark:text-green-400',
  removed: 'text-red-500 dark:text-red-400',
  modified: 'text-yellow-600 dark:text-yellow-400',
};

const CHANGE_BG: Record<string, string> = {
  added: 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800',
  removed: 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800',
  modified: 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800',
};

const CHANGE_BADGE: Record<string, string> = {
  added: 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200',
  removed: 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200',
  modified: 'bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200',
};

// ── Component ──────────────────────────────────────────────────────────────────

export function DiffView({ onNodeSelect, selectedNodeId }: DiffViewProps) {
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [baselineId, setBaselineId] = useState<string>('');
  const [diff, setDiff] = useState<DiffResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterTypes, setFilterTypes] = useState<Set<string>>(new Set(['added', 'removed', 'modified']));
  const [nodeTypeFilter, setNodeTypeFilter] = useState<string>('all');
  const [snapsLoading, setSnapsLoading] = useState(true);

  // Load snapshot list on mount
  useEffect(() => {
    fetch('/api/snapshots')
      .then(r => r.json())
      .then(d => {
        setSnapshots(d.snapshots || []);
        if (d.snapshots?.length > 0) setBaselineId(d.snapshots[0].id);
        setSnapsLoading(false);
      })
      .catch(() => setSnapsLoading(false));
  }, []);

  const handleCompare = () => {
    if (!baselineId) return;
    setLoading(true);
    setError(null);
    fetch(`/api/diff?baseline=${encodeURIComponent(baselineId)}`)
      .then(r => {
        if (!r.ok) return r.json().then(d => Promise.reject(d.error || 'API error'));
        return r.json();
      })
      .then(d => { setDiff(d); setLoading(false); })
      .catch(e => { setError(String(e)); setLoading(false); });
  };

  const toggleFilter = (type: string) => {
    setFilterTypes(prev => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  // ── Empty state: no snapshots ─────────────────────────────────────────────

  if (snapsLoading) {
    return (
      <div className="h-full flex items-center justify-center bg-white dark:bg-gray-900">
        <div className="animate-spin rounded-full h-10 w-10 border-b-4 border-blue-500" />
      </div>
    );
  }

  if (snapshots.length === 0) {
    return (
      <div className="h-full flex items-center justify-center bg-white dark:bg-gray-900 p-8">
        <div className="text-center max-w-md">
          <p className="text-5xl mb-4">📸</p>
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">No snapshots yet</h2>
          <p className="text-gray-500 dark:text-gray-400 mb-4">
            Create a baseline snapshot to compare graphs over time.
          </p>
          <pre className="text-left bg-gray-100 dark:bg-gray-800 rounded-lg p-4 text-sm font-mono text-gray-700 dark:text-gray-300">
{`flask-brain snapshot ./my-project \\
  --label "Before refactor"`}
          </pre>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-3">
            After creating a snapshot, scan again and return here to see what changed.
          </p>
        </div>
      </div>
    );
  }

  // ── Compute filtered results ───────────────────────────────────────────────

  const allNodeTypes = diff
    ? [...new Set(diff.node_changes.map(nc => (nc.new_node || nc.old_node)?.type || 'unknown'))]
    : [];

  const filteredNodeChanges = diff?.node_changes.filter(nc => {
    if (!filterTypes.has(nc.change_type)) return false;
    if (nodeTypeFilter !== 'all') {
      const nodeType = (nc.new_node || nc.old_node)?.type;
      if (nodeType !== nodeTypeFilter) return false;
    }
    return true;
  }) ?? [];

  const filteredEdgeChanges = diff?.edge_changes.filter(ec => filterTypes.has(ec.change_type)) ?? [];

  const totalChanges = filteredNodeChanges.length + filteredEdgeChanges.length;

  // ── Main UI ───────────────────────────────────────────────────────────────

  return (
    <div className="h-full overflow-y-auto bg-white dark:bg-gray-900 p-6">
      <div className="max-w-5xl mx-auto space-y-6">

        {/* Header */}
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-1 flex items-center gap-2">
            <span>📊</span> Diff Mode
          </h2>
          <p className="text-gray-500 dark:text-gray-400 text-sm">
            Compare the current graph against a saved snapshot to see what changed.
          </p>
        </div>

        {/* Baseline selector + compare button */}
        <div className="flex items-end gap-3 flex-wrap">
          <div className="flex-1 min-w-48">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Baseline snapshot
            </label>
            <select
              value={baselineId}
              onChange={e => { setBaselineId(e.target.value); setDiff(null); }}
              className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {snapshots.map(s => (
                <option key={s.id} value={s.id}>
                  {s.id}{s.label ? ` — ${s.label}` : ''} ({s.node_count} nodes)
                </option>
              ))}
            </select>
          </div>

          <div className="text-gray-400 dark:text-gray-500 text-sm pb-2">vs</div>

          <div className="flex-1 min-w-32">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Compare to
            </label>
            <div className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 text-gray-600 dark:text-gray-400 px-3 py-2 text-sm">
              Current scan
            </div>
          </div>

          <button
            onClick={handleCompare}
            disabled={loading || !baselineId}
            className="px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {loading ? 'Comparing…' : 'Compare'}
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300 text-sm">
            Error: {error}
          </div>
        )}

        {/* Results */}
        {diff && (
          <>
            {/* Summary badges */}
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
              {([
                ['nodes_added', 'Nodes Added', 'text-green-600 dark:text-green-400', 'bg-green-50 dark:bg-green-900/20'],
                ['nodes_removed', 'Nodes Removed', 'text-red-600 dark:text-red-400', 'bg-red-50 dark:bg-red-900/20'],
                ['nodes_modified', 'Nodes Modified', 'text-yellow-600 dark:text-yellow-400', 'bg-yellow-50 dark:bg-yellow-900/20'],
                ['edges_added', 'Edges Added', 'text-green-600 dark:text-green-400', 'bg-green-50 dark:bg-green-900/20'],
                ['edges_removed', 'Edges Removed', 'text-red-600 dark:text-red-400', 'bg-red-50 dark:bg-red-900/20'],
              ] as const).map(([key, label, tc, bg]) => (
                <div key={key} className={`${bg} rounded-lg p-3 text-center`}>
                  <div className={`text-2xl font-bold ${tc}`}>{diff.summary[key as keyof DiffSummary]}</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{label}</div>
                </div>
              ))}
            </div>

            {/* Filter controls */}
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-sm text-gray-500 dark:text-gray-400">Show:</span>
              {(['added', 'removed', 'modified'] as const).map(type => (
                <button
                  key={type}
                  onClick={() => toggleFilter(type)}
                  className={`px-3 py-1 rounded-full text-xs font-medium border transition-all capitalize ${
                    filterTypes.has(type)
                      ? CHANGE_BADGE[type]
                      : 'bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-600 border-gray-200 dark:border-gray-700'
                  }`}
                >
                  {CHANGE_ICONS[type]} {type}
                </button>
              ))}
              {allNodeTypes.length > 1 && (
                <select
                  value={nodeTypeFilter}
                  onChange={e => setNodeTypeFilter(e.target.value)}
                  className="ml-auto rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 px-2 py-1 text-xs focus:outline-none"
                >
                  <option value="all">All types</option>
                  {allNodeTypes.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              )}
            </div>

            {/* No changes message */}
            {totalChanges === 0 && (
              <div className="text-center py-12">
                <p className="text-4xl mb-3">✅</p>
                <p className="text-lg font-semibold text-gray-900 dark:text-white">No visible changes</p>
                <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
                  {diff.summary.nodes_added + diff.summary.nodes_removed + diff.summary.nodes_modified === 0
                    ? 'The graphs are identical.'
                    : 'Try adjusting the filters above.'}
                </p>
              </div>
            )}

            {/* Node changes */}
            {filteredNodeChanges.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide mb-2">
                  Node Changes ({filteredNodeChanges.length})
                </h3>
                <div className="space-y-2">
                  {filteredNodeChanges.map(nc => {
                    const node = nc.new_node || nc.old_node;
                    const fp = node?.file_path || '';
                    const ln = node?.line_number;
                    const loc = ln ? `${fp}:${ln}` : fp;
                    const isSelected = nc.node_id === selectedNodeId;
                    const nodeForSelect = nc.new_node || nc.old_node;

                    return (
                      <div
                        key={nc.node_id}
                        className={`rounded-lg border p-3 ${CHANGE_BG[nc.change_type]} ${
                          isSelected ? 'ring-2 ring-blue-400' : ''
                        }`}
                      >
                        <div className="flex items-start gap-2">
                          <span className={`text-sm font-bold shrink-0 w-5 text-center ${CHANGE_COLORS[nc.change_type]}`}>
                            {CHANGE_ICONS[nc.change_type]}
                          </span>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-baseline gap-2 flex-wrap">
                              <span className="font-mono text-sm text-gray-900 dark:text-white font-medium truncate">
                                {nc.node_id}
                              </span>
                              {node?.type && (
                                <span className="text-xs text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded font-mono">
                                  {node.type}
                                </span>
                              )}
                            </div>
                            {loc && (
                              <div className="text-xs text-gray-400 dark:text-gray-500 mt-0.5 truncate">{loc}</div>
                            )}
                            {/* Modified field diffs */}
                            {nc.change_type === 'modified' && Object.keys(nc.changes).length > 0 && (
                              <div className="mt-1.5 space-y-0.5">
                                {Object.entries(nc.changes)
                                  .filter(([f]) => f !== 'metadata')
                                  .map(([f, vals]) => (
                                    <div key={f} className="text-xs font-mono text-gray-600 dark:text-gray-400">
                                      <span className="text-gray-400">{f}:</span>{' '}
                                      <span className="text-red-500 line-through">{String(vals.old)}</span>
                                      {' → '}
                                      <span className="text-green-600 dark:text-green-400">{String(vals.new)}</span>
                                    </div>
                                  ))}
                                {nc.changes.metadata && (
                                  <div className="text-xs text-gray-500 dark:text-gray-400 italic">metadata changed</div>
                                )}
                              </div>
                            )}
                          </div>
                          {/* Navigate button — only for nodes that exist in current graph */}
                          {nc.change_type !== 'removed' && nodeForSelect && (
                            <button
                              onClick={() => onNodeSelect(nodeForSelect as Node)}
                              className="shrink-0 text-xs text-blue-600 dark:text-blue-400 hover:underline"
                            >
                              View →
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Edge changes */}
            {filteredEdgeChanges.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide mb-2">
                  Edge Changes ({filteredEdgeChanges.length})
                </h3>
                <div className="space-y-1.5">
                  {filteredEdgeChanges.map((ec, i) => (
                    <div
                      key={i}
                      className={`rounded-lg border p-2.5 flex items-center gap-2 ${CHANGE_BG[ec.change_type]}`}
                    >
                      <span className={`text-sm font-bold shrink-0 w-5 text-center ${CHANGE_COLORS[ec.change_type]}`}>
                        {CHANGE_ICONS[ec.change_type]}
                      </span>
                      <span className="font-mono text-xs text-gray-800 dark:text-gray-200 truncate">
                        {ec.source}
                        <span className="text-gray-400 mx-1">→</span>
                        {ec.target}
                      </span>
                      <span className="ml-auto shrink-0 text-xs text-gray-500 dark:text-gray-400 font-mono bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded">
                        {ec.edge_type}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
