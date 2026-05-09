import { NODE_COLORS } from '../utils/cytoscapeStyles';
import type { NodeType } from '../types/graph';

interface GraphToolbarProps {
  layout: string;
  onLayoutChange: (layout: string) => void;
  onFit: () => void;
  onExportPNG: () => void;
  visibleNodeTypes: Set<NodeType>;
  onNodeTypeToggle: (type: NodeType) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  clusterByBlueprint: boolean;
  onClusterToggle: () => void;
}

const NODE_TYPE_LABELS: Record<NodeType, string> = {
  blueprint: 'Blueprint',
  route: 'Route',
  action: 'Action',
  service: 'Service',
  model: 'Model',
  task: 'Task',
};

export function GraphToolbar({
  layout,
  onLayoutChange,
  onFit,
  onExportPNG,
  visibleNodeTypes,
  onNodeTypeToggle,
  searchQuery,
  onSearchChange,
  clusterByBlueprint,
  onClusterToggle,
}: GraphToolbarProps) {
  const nodeTypes: NodeType[] = ['blueprint', 'route', 'action', 'service', 'model', 'task'];

  return (
    <div className="absolute top-4 left-4 z-10 bg-white dark:bg-gray-800 rounded-lg shadow-lg p-3 flex flex-col gap-3 max-w-2xl">
      {/* First row: Layout, Fit, Export */}
      <div className="flex items-center gap-2">
        <select
          value={layout}
          onChange={(e) => onLayoutChange(e.target.value)}
          className="px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="dagre">Hierarchical</option>
          <option value="cose-bilkent">Force-Directed</option>
          <option value="breadthfirst">Breadth-First</option>
          <option value="circle">Circle</option>
        </select>

        <button
          onClick={onFit}
          className="px-3 py-2 bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 border border-gray-300 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white transition-colors"
          title="Fit to view"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
          </svg>
        </button>

        <button
          onClick={onExportPNG}
          className="px-3 py-2 bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 border border-gray-300 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white transition-colors"
          title="Export as PNG"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
        </button>
      </div>

      {/* Second row: Node type filters */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs text-gray-600 dark:text-gray-400 font-semibold mr-1">Filter:</span>
        {nodeTypes.map((type) => {
          const isVisible = visibleNodeTypes.has(type);
          return (
            <button
              key={type}
              onClick={() => onNodeTypeToggle(type)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border-2 ${
                isVisible
                  ? 'text-white shadow-md'
                  : 'text-gray-400 dark:text-gray-500 bg-gray-100 dark:bg-gray-700 border-gray-300 dark:border-gray-600 opacity-50'
              }`}
              style={{
                backgroundColor: isVisible ? NODE_COLORS[type] : undefined,
                borderColor: isVisible ? NODE_COLORS[type] : undefined,
              }}
              title={`Toggle ${NODE_TYPE_LABELS[type]} nodes`}
            >
              {NODE_TYPE_LABELS[type]}
            </button>
          );
        })}
      </div>

      {/* Third row: Search and cluster */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search nodes by name..."
            className="w-full px-3 py-2 pl-9 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <svg
            className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>

        <button
          onClick={onClusterToggle}
          className={`px-3 py-2 rounded-lg text-sm font-semibold transition-all border-2 whitespace-nowrap ${
            clusterByBlueprint
              ? 'bg-blue-500 text-white border-blue-500 shadow-md'
              : 'bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-600'
          }`}
          title="Toggle blueprint clustering"
        >
          {clusterByBlueprint ? '✓ Clustered' : 'Cluster by Blueprint'}
        </button>
      </div>
    </div>
  );
}
