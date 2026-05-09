import { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';
import { generateSequenceDiagram } from '../utils/mermaid';
import { useGraph } from '../hooks/useGraph';
import type { Node } from '../types/graph';

interface SequenceDiagramModalProps {
  routeNode: Node;
  onClose: () => void;
}

function SequenceDiagramModal({ routeNode, onClose }: SequenceDiagramModalProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [diagramSrc, setDiagramSrc] = useState<string | null>(null);

  const safeRouteId = routeNode.id
    .replace('::', '_').replace(/\//g, '_').replace(/ /g, '_')
    .replace(/</g, '').replace(/>/g, '').replace(/:/g, '_');

  const { graph, loading } = useGraph(`/api/graph/${safeRouteId}`);

  useEffect(() => {
    if (!graph) return;

    const render = async () => {
      try {
        mermaid.initialize({
          startOnLoad: false,
          theme: document.documentElement.classList.contains('dark') ? 'dark' : 'default',
          securityLevel: 'loose',
          sequence: {
            diagramMarginX: 40,
            diagramMarginY: 20,
            actorMargin: 80,
            width: 180,
            height: 50,
            boxMargin: 10,
            useMaxWidth: true,
          },
        });

        const code = generateSequenceDiagram(graph, routeNode);
        setDiagramSrc(code);
        console.debug('[SequenceDiagram]\n', code);

        const id = `mermaid-seq-${Date.now()}`;
        const { svg } = await mermaid.render(id, code);

        if (containerRef.current) {
          containerRef.current.innerHTML = svg;
          // Make the SVG scale to fill the container
          const svgEl = containerRef.current.querySelector('svg');
          if (svgEl) {
            svgEl.style.width = '100%';
            svgEl.style.height = 'auto';
            svgEl.style.maxWidth = '100%';
          }
        }
        setError(null);
      } catch (err) {
        console.error('[SequenceDiagram] render error:', err);
        setError(`Mermaid error: ${err instanceof Error ? err.message : String(err)}`);
      }
    };

    render();
  }, [graph, routeNode]);

  const handleExport = () => {
    if (!containerRef.current) return;
    const svg = containerRef.current.querySelector('svg');
    if (!svg) return;
    const blob = new Blob([new XMLSerializer().serializeToString(svg)], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `sequence-${(routeNode.metadata?.view_function ?? routeNode.label).replace(/[^a-zA-Z0-9]/g, '-')}.svg`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleCopySource = () => {
    if (diagramSrc) navigator.clipboard.writeText(diagramSrc);
  };

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl flex flex-col w-[90vw] h-[85vh] overflow-hidden">
        {/* Modal header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
          <div>
            <h2 className="text-lg font-bold text-gray-900 dark:text-white">Sequence Diagram</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 font-mono mt-0.5">
              {routeNode.label}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {diagramSrc && (
              <button
                onClick={handleCopySource}
                className="px-3 py-1.5 text-xs bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg transition-colors font-mono"
                title="Copy Mermaid source"
              >
                Copy source
              </button>
            )}
            <button
              onClick={handleExport}
              className="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
            >
              Export SVG
            </button>
            <button
              onClick={onClose}
              className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              title="Close (Esc)"
            >
              <svg className="h-5 w-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Diagram area */}
        <div className="flex-1 overflow-auto p-6">
          {loading && (
            <div className="flex items-center justify-center h-full">
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600" />
            </div>
          )}

          {error && !loading && (
            <div className="space-y-4">
              <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
                <p className="text-sm font-semibold text-red-800 dark:text-red-200 mb-1">Render error</p>
                <p className="text-xs text-red-700 dark:text-red-300 font-mono">{error}</p>
              </div>
              {diagramSrc && (
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mb-2 font-semibold">Generated Mermaid source:</p>
                  <pre className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 text-xs font-mono overflow-auto whitespace-pre">
                    {diagramSrc}
                  </pre>
                </div>
              )}
            </div>
          )}

          {!loading && !error && (
            <div
              ref={containerRef}
              className="w-full flex justify-center"
            />
          )}
        </div>
      </div>
    </div>
  );
}

// ── Inline trigger shown in the Sidebar ─────────────────────────────────────

interface SequenceDiagramProps {
  routeNode: Node;
}

export function SequenceDiagram({ routeNode }: SequenceDiagramProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Sequence Diagram</h4>
        <button
          onClick={() => setOpen(true)}
          className="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors flex items-center gap-1"
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
          </svg>
          View full diagram
        </button>
      </div>
      <p className="text-xs text-gray-500 dark:text-gray-400">
        Shows request flow: client → handler → services → models
      </p>

      {open && (
        <SequenceDiagramModal routeNode={routeNode} onClose={() => setOpen(false)} />
      )}
    </>
  );
}
