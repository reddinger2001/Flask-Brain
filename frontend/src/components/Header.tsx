import { useState, useEffect } from 'react';
import type { Manifest } from '../types/graph';

interface HeaderProps {
  manifest: Manifest | null;
  onRescan: () => void;
  isRescanning: boolean;
  onThemeToggle: () => void;
  isDark: boolean;
}

export function Header({ manifest, onRescan, isRescanning, onThemeToggle, isDark }: HeaderProps) {
  const [timeAgo, setTimeAgo] = useState<string>('');

  useEffect(() => {
    if (!manifest?.scan_timestamp) return;

    const updateTimeAgo = () => {
      const scanTime = new Date(manifest.scan_timestamp);
      const now = new Date();
      const diffMs = now.getTime() - scanTime.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      
      if (diffMins < 1) {
        setTimeAgo('just now');
      } else if (diffMins === 1) {
        setTimeAgo('1 minute ago');
      } else if (diffMins < 60) {
        setTimeAgo(`${diffMins} minutes ago`);
      } else {
        const diffHours = Math.floor(diffMins / 60);
        setTimeAgo(diffHours === 1 ? '1 hour ago' : `${diffHours} hours ago`);
      }
    };

    updateTimeAgo();
    const interval = setInterval(updateTimeAgo, 30000); // Update every 30 seconds

    return () => clearInterval(interval);
  }, [manifest?.scan_timestamp]);

  return (
    <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <span className="text-3xl">🧠</span>
            Flask Brain
          </h1>
          {manifest && (
            <div className="flex items-center gap-4 text-sm">
              <span className="text-gray-600 dark:text-gray-400">
                {manifest.project_name}
              </span>
              <span className="text-gray-400 dark:text-gray-500">•</span>
              <span className="text-gray-500 dark:text-gray-400">
                Last scanned: {timeAgo}
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-4">
          {manifest && (
            <div className="flex items-center gap-4 text-sm">
              <div className="flex items-center gap-2">
                <span className="text-gray-500 dark:text-gray-400">Nodes:</span>
                <span className="font-semibold text-gray-900 dark:text-white">{manifest.node_count}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-gray-500 dark:text-gray-400">Edges:</span>
                <span className="font-semibold text-gray-900 dark:text-white">{manifest.edge_count}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-gray-500 dark:text-gray-400">Routes:</span>
                <span className="font-semibold text-gray-900 dark:text-white">{manifest.node_types.route || 0}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-gray-500 dark:text-gray-400">Models:</span>
                <span className="font-semibold text-gray-900 dark:text-white">{manifest.node_types.model || 0}</span>
              </div>
            </div>
          )}

          <button
            onClick={onRescan}
            disabled={isRescanning}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
          >
            {isRescanning ? (
              <>
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Rescanning...
              </>
            ) : (
              <>
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Rescan
              </>
            )}
          </button>

          <button
            onClick={onThemeToggle}
            className="p-2 rounded-lg bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
            aria-label="Toggle theme"
          >
            {isDark ? (
              <svg className="h-5 w-5 text-yellow-500" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" clipRule="evenodd" />
              </svg>
            ) : (
              <svg className="h-5 w-5 text-gray-700" fill="currentColor" viewBox="0 0 20 20">
                <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
              </svg>
            )}
          </button>
        </div>
      </div>
    </header>
  );
}
