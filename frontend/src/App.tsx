import { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { GraphCanvas } from './components/GraphCanvas';
import { RouteMap } from './components/RouteMap';
import { ERDView } from './components/ERDView';
import { HeatmapView } from './components/HeatmapView';
import { DeadWeightView } from './components/DeadWeightView';
import { BlindSpotsView } from './components/BlindSpotsView';
import { SearchView } from './components/SearchView';
import { RiskView } from './components/RiskView';
import { DiffView } from './components/DiffView';
import ClassDiagram from './components/ClassDiagram';
import { ComponentDiagram } from './components/ComponentDiagram';
import { SequenceDiagramView } from './components/SequenceDiagramView';
import { useGraph, useManifest } from './hooks/useGraph';
import { useSSE } from './hooks/useSSE';
import type { Node } from './types/graph';

type TabType = 'graph' | 'routes' | 'erd' | 'heatmap' | 'deadweight' | 'blindspots' | 'search' | 'risk' | 'diff' | 'classdiagram' | 'componentdiagram' | 'sequence';

function App() {
  const [activeTab, setActiveTab] = useState<TabType>('graph');
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [navigateToNode, setNavigateToNode] = useState<Node | null>(null);
  const [isDark, setIsDark] = useState(true);
  const [isRescanning, setIsRescanning] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const { manifest, refetch: refetchManifest } = useManifest();
  const { graph, loading, error, refetch: refetchGraph } = useGraph('/api/graph/all');

  // Theme management
  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDark]);

  // SSE for watch mode
  useSSE(() => {
    showToast('Graph updated');
    refetchManifest();
    refetchGraph();
  });

  const handleRescan = async () => {
    setIsRescanning(true);
    try {
      const response = await fetch('/api/scan', { method: 'POST' });
      if (response.ok) {
        showToast('Rescan complete');
        await refetchManifest();
        await refetchGraph();
      } else {
        showToast('Rescan failed');
      }
    } catch (err) {
      console.error('Rescan error:', err);
      showToast('Rescan failed');
    } finally {
      setIsRescanning(false);
    }
  };

  const showToast = (message: string) => {
    setToast(message);
    setTimeout(() => setToast(null), 3000);
  };

  const handleNodeSelect = (node: Node | null) => {
    setSelectedNode(node);
  };

  const handleRouteSelect = (routeNode: Node) => {
    setActiveTab('graph');
    setSelectedNode(routeNode);
    setNavigateToNode(routeNode);
    // Reset navigateToNode after a delay so repeat clicks still trigger the effect
    setTimeout(() => setNavigateToNode(null), 500);
  };

  const handleHeatmapNodeSelect = (node: Node) => {
    setActiveTab('graph');
    setSelectedNode(node);
    setNavigateToNode(node);
    // Reset navigateToNode after a delay so repeat clicks still trigger the effect
    setTimeout(() => setNavigateToNode(null), 500);
  };

  if (loading) {
    return (
      <div className="w-full h-screen flex items-center justify-center bg-white dark:bg-gray-900">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-lg text-gray-600 dark:text-gray-400">Loading graph data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full h-screen flex items-center justify-center bg-white dark:bg-gray-900">
        <div className="text-center max-w-md">
          <svg className="mx-auto h-16 w-16 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h2 className="mt-4 text-xl font-semibold text-gray-900 dark:text-white">Failed to load graph</h2>
          <p className="mt-2 text-gray-600 dark:text-gray-400">{error}</p>
          <p className="mt-4 text-sm text-gray-500 dark:text-gray-500">
            Make sure the Flask Brain backend is running at <code className="bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded">http://localhost:7891</code>
          </p>
          <button
            onClick={() => window.location.reload()}
            className="mt-6 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!graph) {
    return null;
  }

  return (
    <div className="w-full h-screen flex flex-col bg-white dark:bg-gray-900">
      {/* Header */}
      <Header
        manifest={manifest}
        onRescan={handleRescan}
        isRescanning={isRescanning}
        onThemeToggle={() => setIsDark(!isDark)}
        isDark={isDark}
      />

      {/* Tab Bar */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6">
        <div className="flex gap-1">
          {[
            { id: 'graph' as TabType, label: 'Graph', icon: '🕸️' },
            { id: 'classdiagram' as TabType, label: 'Class Diagram', icon: '📐' },
            { id: 'componentdiagram' as TabType, label: 'Components', icon: '🧩' },
            { id: 'sequence' as TabType, label: 'Sequence', icon: '📋' },
            { id: 'routes' as TabType, label: 'Route Map', icon: '🗺️' },
            { id: 'erd' as TabType, label: 'ERD', icon: '🗄️' },
            { id: 'heatmap' as TabType, label: 'Heatmap', icon: '🔥' },
            { id: 'deadweight' as TabType, label: 'Dead Weight', icon: '💀' },
            { id: 'blindspots' as TabType, label: 'Blind Spots', icon: '🔍' },
            { id: 'search' as TabType, label: 'Search', icon: '🔎' },
            { id: 'risk' as TabType, label: 'Risk', icon: '🔥' },
            { id: 'diff' as TabType, label: 'Diff', icon: '📊' },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-3 font-medium transition-colors border-b-2 ${
                activeTab === tab.id
                  ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              }`}
            >
              <span className="mr-2">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* View Area */}
        <div className="flex-1 overflow-hidden">
          {activeTab === 'graph' && (
            <GraphCanvas
              graph={graph}
              onNodeSelect={handleNodeSelect}
              selectedNodeId={selectedNode?.id || null}
              navigateTo={navigateToNode}
              manifest={manifest}
            />
          )}
          {activeTab === 'classdiagram' && (
            <ClassDiagram graph={graph} onNodeSelect={handleNodeSelect} selectedNodeId={selectedNode?.id || null} />
          )}
          {activeTab === 'componentdiagram' && (
            <ComponentDiagram graph={graph} onNodeSelect={handleNodeSelect} selectedNodeId={selectedNode?.id || null} />
          )}
          {activeTab === 'sequence' && (
            <SequenceDiagramView graph={graph} onNodeSelect={handleNodeSelect} selectedNodeId={selectedNode?.id || null} />
          )}
          {activeTab === 'routes' && (
            <RouteMap graph={graph} onRouteSelect={handleRouteSelect} selectedNodeId={selectedNode?.id || null} />
          )}
          {activeTab === 'erd' && (
            <ERDView graph={graph} onNodeSelect={handleNodeSelect} selectedNodeId={selectedNode?.id || null} />
          )}
          {activeTab === 'heatmap' && (
            <HeatmapView graph={graph} onNodeSelect={handleHeatmapNodeSelect} selectedNodeId={selectedNode?.id || null} />
          )}
          {activeTab === 'deadweight' && (
            <DeadWeightView onNodeSelect={handleHeatmapNodeSelect} selectedNodeId={selectedNode?.id || null} />
          )}
          {activeTab === 'blindspots' && (
            <BlindSpotsView onNodeSelect={handleHeatmapNodeSelect} selectedNodeId={selectedNode?.id || null} />
          )}
          {activeTab === 'search' && (
            <SearchView onNodeSelect={handleHeatmapNodeSelect} selectedNodeId={selectedNode?.id || null} />
          )}
          {activeTab === 'risk' && (
            <RiskView onNodeSelect={handleHeatmapNodeSelect} selectedNodeId={selectedNode?.id || null} />
          )}
          {activeTab === 'diff' && (
            <DiffView onNodeSelect={handleHeatmapNodeSelect} selectedNodeId={selectedNode?.id || null} />
          )}
        </div>

        {/* Sidebar */}
        {selectedNode && (
          <Sidebar node={selectedNode} onClose={() => setSelectedNode(null)} onNavigate={handleHeatmapNodeSelect} />
        )}
      </div>

      {/* Toast Notification */}
      {toast && (
        <div className="fixed bottom-4 right-4 bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900 px-6 py-3 rounded-lg shadow-lg flex items-center gap-2 animate-fade-in z-50">
          <svg className="h-5 w-5 text-green-400 dark:text-green-600" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
          {toast}
        </div>
      )}
    </div>
  );
}

export default App;
