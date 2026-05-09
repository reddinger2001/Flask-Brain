import { useState, useEffect } from 'react';
import type { Node } from '../types/graph';

interface RiskResponse {
  count: number;
  nodes: Node[];
}

interface RiskViewProps {
  onNodeSelect: (node: Node) => void;
  selectedNodeId?: string | null;
}

const TYPE_BADGE: Record<string, string> = {
  action: 'bg-blue-200 dark:bg-blue-800 text-blue-900 dark:text-blue-100',
  service: 'bg-purple-200 dark:bg-purple-800 text-purple-900 dark:text-purple-100',
  task: 'bg-orange-200 dark:bg-orange-800 text-orange-900 dark:text-orange-100',
  route: 'bg-green-200 dark:bg-green-800 text-green-900 dark:text-green-100',
  model: 'bg-red-200 dark:bg-red-800 text-red-900 dark:text-red-100',
};

type SortKey = 'risk_score' | 'churn_count' | 'complexity';

function riskColor(score: number, max: number): string {
  const ratio = max > 0 ? score / max : 0;
  if (ratio > 0.66) return 'bg-red-500';
  if (ratio > 0.33) return 'bg-orange-400';
  return 'bg-yellow-400';
}

function riskLabel(score: number, max: number): string {
  const ratio = max > 0 ? score / max : 0;
  if (ratio > 0.66) return 'HIGH';
  if (ratio > 0.33) return 'MED';
  return 'LOW';
}

function riskBadgeColor(score: number, max: number): string {
  const ratio = max > 0 ? score / max : 0;
  if (ratio > 0.66) return 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300';
  if (ratio > 0.33) return 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300';
  return 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300';
}

export function RiskView({ onNodeSelect, selectedNodeId }: RiskViewProps) {
  const [data, setData] = useState<RiskResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<SortKey>('risk_score');

  useEffect(() => {
    setLoading(true);
    fetch('/api/analysis/risk')
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-white dark:bg-gray-900">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-4 border-red-500 mx-auto"></div>
          <p className="mt-4 text-gray-600 dark:text-gray-400">Calculating risk scores…</p>
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

  const maxScore = Math.max(1, ...data.nodes.map(n => n.metadata?.risk_score ?? 0));

  const sorted = [...data.nodes].sort((a, b) => {
    const va = (a.metadata?.[sortBy as keyof typeof a.metadata] ?? 0) as number;
    const vb = (b.metadata?.[sortBy as keyof typeof b.metadata] ?? 0) as number;
    return vb - va;
  });

  const SortBtn = ({ k, label }: { k: SortKey; label: string }) => (
    <button
      onClick={() => setSortBy(k)}
      className={`px-3 py-1 rounded text-sm font-medium transition-all ${
        sortBy === k
          ? 'bg-red-600 text-white'
          : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="h-full overflow-y-auto bg-white dark:bg-gray-900 p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2 flex items-center gap-2">
            <span>🔥</span> Risk Score Leaderboard
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            Top <strong>{data.count}</strong> nodes ranked by{' '}
            <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded text-sm">risk_score = complexity × git_churn</code>.
            High churn + high complexity = highest deployment risk.
          </p>
        </div>

        {/* Sort controls */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm text-gray-500 dark:text-gray-400 mr-1">Sort by:</span>
          <SortBtn k="risk_score" label="Risk Score" />
          <SortBtn k="churn_count" label="Git Churn" />
          <SortBtn k="complexity" label="Complexity" />
        </div>

        {/* Table */}
        {sorted.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-4xl mb-4">✅</p>
            <p className="text-lg font-semibold text-gray-900 dark:text-white">No risk data available</p>
            <p className="text-gray-500 dark:text-gray-400 mt-1">
              Make sure the project is inside a git repo and has been scanned with flask-brain.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {sorted.map((node, idx) => {
              const score = (node.metadata?.risk_score ?? 0) as number;
              const churn = (node.metadata?.churn_count ?? 0) as number;
              const cx = (node.metadata?.complexity ?? 0) as number;
              const barW = maxScore > 0 ? Math.round((score / maxScore) * 100) : 0;
              const isSelected = node.id === selectedNodeId;

              return (
                <button
                  key={node.id}
                  onClick={() => onNodeSelect(node)}
                  className={`w-full text-left p-3 rounded-lg border transition-all ${
                    isSelected
                      ? 'bg-red-50 dark:bg-red-900/20 border-red-400 dark:border-red-600'
                      : 'bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-750'
                  }`}
                >
                  {/* Row top: rank + type + label + risk badge */}
                  <div className="flex items-start gap-3 mb-2">
                    <span className="text-xs font-mono text-gray-400 dark:text-gray-500 w-6 shrink-0 pt-0.5">
                      #{idx + 1}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-xs font-mono font-bold shrink-0 ${TYPE_BADGE[node.type] || 'bg-gray-200 dark:bg-gray-700 text-gray-800'}`}>
                      {node.type}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-gray-900 dark:text-white truncate">
                        {node.label}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400 truncate mt-0.5">
                        {node.file_path}{node.line_number ? `:${node.line_number}` : ''}
                      </div>
                    </div>
                    {/* Risk label badge */}
                    <span className={`shrink-0 text-xs font-bold px-2 py-0.5 rounded ${riskBadgeColor(score, maxScore)}`}>
                      {riskLabel(score, maxScore)}
                    </span>
                  </div>

                  {/* Risk bar */}
                  <div className="ml-9 flex items-center gap-3">
                    <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${riskColor(score, maxScore)}`}
                        style={{ width: `${barW}%` }}
                      />
                    </div>
                    <div className="flex gap-3 text-xs font-mono text-gray-500 dark:text-gray-400 shrink-0">
                      <span title="Risk score">⚠ {score}</span>
                      <span title="Git commit churn">🔄 {churn}</span>
                      <span title="Cyclomatic complexity">⚙ {cx}</span>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}

        {/* Legend */}
        <div className="flex gap-4 text-xs text-gray-500 dark:text-gray-400 pt-2 border-t border-gray-200 dark:border-gray-700">
          <span>⚠ risk_score</span>
          <span>🔄 git churn (commits)</span>
          <span>⚙ cyclomatic complexity</span>
        </div>
      </div>
    </div>
  );
}
