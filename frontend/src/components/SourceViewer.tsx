import { useEffect, useState } from 'react';
import type { SourceResponse } from '../types/graph';

interface SourceViewerProps {
  filePath: string;
  lineNumber: number;
  onClose: () => void;
}

export function SourceViewer({ filePath, lineNumber, onClose }: SourceViewerProps) {
  const [source, setSource] = useState<SourceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchSource = async () => {
      setLoading(true);
      setError(null);
      
      try {
        const response = await fetch(`/api/source?path=${encodeURIComponent(filePath)}&line=${lineNumber}`);
        if (!response.ok) {
          throw new Error(`Failed to fetch source: ${response.statusText}`);
        }
        
        const data = await response.json();
        setSource(data);
      } catch (err) {
        console.error('Error fetching source:', err);
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchSource();
  }, [filePath, lineNumber]);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-2xl max-w-4xl w-full max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Source Code</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">{filePath}</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
          >
            <svg className="h-5 w-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            </div>
          )}

          {error && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
              <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
              <p className="text-xs text-red-600 dark:text-red-300 mt-2">
                This feature requires the backend to implement the /api/source endpoint.
              </p>
            </div>
          )}

          {source && (
            <div className="bg-gray-50 dark:bg-gray-900 rounded-lg overflow-hidden">
              <pre className="p-4 text-sm font-mono overflow-x-auto">
                {source.content.split('\n').map((line, idx) => {
                  const currentLine = idx + 1;
                  const isTargetLine = currentLine === lineNumber;
                  
                  return (
                    <div
                      key={idx}
                      className={`${
                        isTargetLine
                          ? 'bg-yellow-200 dark:bg-yellow-900/50 font-semibold'
                          : ''
                      }`}
                    >
                      <span className="inline-block w-12 text-right pr-4 text-gray-500 dark:text-gray-400 select-none">
                        {currentLine}
                      </span>
                      <span className="text-gray-900 dark:text-gray-100">{line}</span>
                    </div>
                  );
                })}
              </pre>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-gray-200 dark:border-gray-700 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-900 dark:text-white rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
