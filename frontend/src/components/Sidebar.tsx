import { useState } from 'react';
import { NODE_COLORS, COMPLEXITY_COLORS } from '../utils/cytoscapeStyles';
import type { Node, Graph } from '../types/graph';
import { SequenceDiagram } from './SequenceDiagram';
import { SourceViewer } from './SourceViewer';

interface SidebarProps {
  node: Node | null;
  onClose: () => void;
  onNavigate?: (node: Node) => void;
}

export function Sidebar({ node, onClose, onNavigate }: SidebarProps) {
  const [showSource, setShowSource] = useState(false);
  const [copyFeedback, setCopyFeedback] = useState(false);
  const [impactData, setImpactData] = useState<Graph | null>(null);
  const [impactLoading, setImpactLoading] = useState(false);
  const [showImpact, setShowImpact] = useState(false);

  if (!node) return null;

  const handleImpactAnalysis = async () => {
    if (showImpact && impactData) { setShowImpact(false); return; }
    setImpactLoading(true);
    setShowImpact(true);
    try {
      const res = await fetch(`/api/analysis/impact?nodeId=${encodeURIComponent(node.id)}`);
      const data = await res.json();
      setImpactData(data);
    } catch (e) {
      console.error('Impact fetch error', e);
    } finally {
      setImpactLoading(false);
    }
  };

  const handleCopyContext = async () => {
    try {
      const response = await fetch(`/api/context?nodeId=${encodeURIComponent(node.id)}`);
      if (!response.ok) throw new Error('Failed to fetch context');
      
      const data = await response.json();
      const context = data.context ?? JSON.stringify(data, null, 2);
      await navigator.clipboard.writeText(context);
      
      setCopyFeedback(true);
      setTimeout(() => setCopyFeedback(false), 2000);
    } catch (error) {
      console.error('Error copying context:', error);
      alert('Failed to copy AI context: ' + (error instanceof Error ? error.message : String(error)));
    }
  };

  const getMethodBadgeColor = (method: string) => {
    switch (method.toUpperCase()) {
      case 'GET': return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
      case 'POST': return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200';
      case 'PUT': return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200';
      case 'DELETE': return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200';
      case 'PATCH': return 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200';
      default: return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200';
    }
  };

  return (
    <>
      <div className="w-96 h-full bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 overflow-y-auto flex flex-col">
        {/* Header */}
        <div className="sticky top-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-4 flex items-center justify-between z-10">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Node Details</h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
          >
            <svg className="h-5 w-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 p-4 space-y-4">
          {/* Type Badge */}
          <div>
            <span
              className="inline-block px-3 py-1 rounded-full text-sm font-semibold text-white"
              style={{ backgroundColor: NODE_COLORS[node.type] }}
            >
              {node.type}
            </span>
          </div>

          {/* Label */}
          <div>
            <h3 className="text-2xl font-bold text-gray-900 dark:text-white break-words">
              {node.label}
            </h3>
          </div>

          {/* File Path */}
          <div>
            <button
              onClick={() => setShowSource(true)}
              className="text-sm text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
              {node.file_path}:{node.line_number}
            </button>
          </div>

          {/* Route-specific metadata */}
          {node.type === 'route' && node.metadata.methods && (
            <div>
              <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">HTTP Methods</h4>
              <div className="flex flex-wrap gap-2">
                {node.metadata.methods.map(method => (
                  <span key={method} className={`px-2 py-1 rounded text-xs font-semibold ${getMethodBadgeColor(method)}`}>
                    {method}
                  </span>
                ))}
              </div>
            </div>
          )}

          {node.type === 'route' && node.metadata.view_function && (
            <div>
              <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">View Function</h4>
              <p className="text-sm text-gray-600 dark:text-gray-400 font-mono">{node.metadata.view_function}</p>
            </div>
          )}

          {node.type === 'route' && node.metadata.blueprint && (
            <div>
              <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Blueprint</h4>
              <p className="text-sm text-gray-600 dark:text-gray-400">{node.metadata.blueprint}</p>
            </div>
          )}

          {/* Action/Service metadata */}
          {(node.type === 'action' || node.type === 'service') && node.metadata.complexity !== undefined && (
            <div className="space-y-2">
              <div>
                <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Complexity</h4>
                <div className="flex items-center gap-2">
                  <span className="text-2xl font-bold text-gray-900 dark:text-white">{node.metadata.complexity}</span>
                  {node.metadata.complexity_tier && (
                    <span
                      className="px-2 py-1 rounded text-xs font-semibold text-white"
                      style={{ backgroundColor: COMPLEXITY_COLORS[node.metadata.complexity_tier] }}
                    >
                      {node.metadata.complexity_tier}
                    </span>
                  )}
                </div>
              </div>
              {node.metadata.line_count !== undefined && (
                <div>
                  <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Lines of Code</h4>
                  <p className="text-sm text-gray-600 dark:text-gray-400">{node.metadata.line_count}</p>
                </div>
              )}
            </div>
          )}

          {/* Service methods */}
          {node.type === 'service' && node.metadata.service_methods && Array.isArray(node.metadata.service_methods) && (
            <div>
              <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Methods</h4>
              <ul className="space-y-1">
                {node.metadata.service_methods.map((method, idx) => (
                  <li key={idx} className="text-sm text-gray-600 dark:text-gray-400 font-mono">• {method}</li>
                ))}
              </ul>
            </div>
          )}

          {node.type === 'service' && node.metadata.is_fat && (
            <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-3">
              <div className="flex items-start gap-2">
                <svg className="h-5 w-5 text-yellow-600 dark:text-yellow-500 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                <div>
                  <p className="text-sm font-semibold text-yellow-800 dark:text-yellow-200">Fat Service</p>
                  <p className="text-xs text-yellow-700 dark:text-yellow-300 mt-1">This service has many methods and may benefit from refactoring.</p>
                </div>
              </div>
            </div>
          )}

          {/* Model metadata */}
          {node.type === 'model' && node.metadata.columns && (
            <div>
              <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Columns</h4>
              <div className="bg-gray-50 dark:bg-gray-900 rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-gray-100 dark:bg-gray-800">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-semibold text-gray-700 dark:text-gray-300">Name</th>
                      <th className="px-3 py-2 text-left text-xs font-semibold text-gray-700 dark:text-gray-300">Type</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {Object.entries(node.metadata.columns).map(([name, info]) => (
                      <tr key={name}>
                        <td className="px-3 py-2 font-mono text-gray-900 dark:text-white">{name}</td>
                        <td className="px-3 py-2 text-gray-600 dark:text-gray-400">{info.type}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {node.type === 'model' && node.metadata.relationships && node.metadata.relationships.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Relationships</h4>
              <ul className="space-y-1">
                {node.metadata.relationships.map((rel, idx) => (
                  <li key={idx} className="text-sm text-gray-600 dark:text-gray-400">• {rel}</li>
                ))}
              </ul>
            </div>
          )}

          {/* DB Operations */}
          {node.metadata.db_operations && node.metadata.db_operations.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Database Operations</h4>
              <ul className="space-y-1">
                {node.metadata.db_operations.map((op, idx) => (
                  <li key={idx} className="text-sm text-gray-600 dark:text-gray-400">
                    <span className={`inline-block w-16 font-semibold ${op.type === 'READ' ? 'text-blue-600 dark:text-blue-400' : 'text-orange-600 dark:text-orange-400'}`}>
                      {op.type}
                    </span>
                    <span className="font-mono">{op.pattern}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Task metadata */}
          {node.type === 'task' && node.metadata.queue && (
            <div>
              <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Queue</h4>
              <p className="text-sm text-gray-600 dark:text-gray-400">{node.metadata.queue}</p>
            </div>
          )}

          {/* Sequence Diagram for routes */}
          {node.type === 'route' && (
            <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
              <SequenceDiagram routeNode={node} />
            </div>
          )}

          {/* Impact Analysis */}
          <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
            <button
              onClick={handleImpactAnalysis}
              className="w-full px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
            >
              <span>⚡</span>
              {showImpact ? 'Hide Impact Analysis' : 'Show Impact Analysis'}
            </button>
            {showImpact && (
              <div className="mt-3 rounded-lg border border-indigo-200 dark:border-indigo-700 overflow-hidden">
                {impactLoading ? (
                  <div className="p-4 text-center text-sm text-gray-500 dark:text-gray-400">
                    <div className="animate-spin inline-block h-5 w-5 border-b-2 border-indigo-500 rounded-full mr-2"></div>
                    Traversing graph…
                  </div>
                ) : impactData ? (
                  <div className="p-3 space-y-1 max-h-64 overflow-y-auto">
                    <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
                      {impactData.nodes.length - 1} dependent node{impactData.nodes.length !== 2 ? 's' : ''} (what breaks if this changes)
                    </p>
                    {impactData.nodes
                      .filter((n: Node) => n.id !== node.id)
                      .map((n: Node) => (
                        <button
                          key={n.id}
                          onClick={() => onNavigate?.(n)}
                          className="w-full text-left flex items-center gap-2 px-2 py-1.5 rounded hover:bg-indigo-50 dark:hover:bg-indigo-900/20 transition-colors"
                        >
                          <span
                            className="w-2 h-2 rounded-full shrink-0"
                            style={{ backgroundColor: NODE_COLORS[n.type] || '#888' }}
                          />
                          <span className="text-xs text-gray-700 dark:text-gray-300 font-mono truncate">{n.label}</span>
                          <span className="text-xs text-gray-400 dark:text-gray-500 shrink-0">{n.type}</span>
                        </button>
                      ))
                    }
                    {impactData.nodes.length === 1 && (
                      <p className="text-xs text-gray-500 dark:text-gray-400 italic">No upstream dependents found.</p>
                    )}
                  </div>
                ) : null}
              </div>
            )}
          </div>

          {/* Copy AI Context Button */}
          <div className="pt-4">
            <button
              onClick={handleCopyContext}
              className="w-full px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
            >
              {copyFeedback ? (
                <>
                  <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                  Copied!
                </>
              ) : (
                <>
                  <span className="text-xl">🤖</span>
                  Copy AI Context
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Source Viewer Modal */}
      {showSource && (
        <SourceViewer
          filePath={node.file_path}
          lineNumber={node.line_number}
          onClose={() => setShowSource(false)}
        />
      )}
    </>
  );
}
