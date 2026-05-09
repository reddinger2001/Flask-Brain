export const NODE_COLORS: Record<string, string> = {
  blueprint: '#009688',
  route: '#4CAF50',
  action: '#2196F3',
  service: '#9C27B0',
  model: '#F44336',
  task: '#FF9800',
};

export const COMPLEXITY_COLORS: Record<string, string> = {
  low: '#4CAF50',
  moderate: '#FFC107',
  high: '#FF9800',
  critical: '#F44336',
};

export const cytoscapeStyles: any[] = [
  // Node styles
  {
    selector: 'node',
    style: {
      'background-color': (ele: any) => NODE_COLORS[ele.data('type')] || '#999',
      'label': 'data(label)',
      'color': '#fff',
      'text-valign': 'center',
      'text-halign': 'center',
      'font-size': '12px',
      'font-weight': 'bold',
      'width': '80px',
      'height': '80px',
      'text-wrap': 'wrap',
      'text-max-width': '70px',
      'border-width': 2,
      'border-color': '#fff',
    },
  },
  {
    selector: 'node:selected',
    style: {
      'border-width': 4,
      'border-color': '#FFD700',
      'overlay-opacity': 0.2,
      'overlay-color': '#FFD700',
    },
  },
  {
    selector: 'node:active',
    style: {
      'overlay-opacity': 0.3,
      'overlay-color': '#FFD700',
    },
  },
  // Edge styles
  {
    selector: 'edge',
    style: {
      'width': 2,
      'line-color': '#999',
      'target-arrow-color': '#999',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      'arrow-scale': 1.5,
    },
  },
  {
    selector: 'edge[type="calls"]',
    style: {
      'line-style': 'solid',
      'line-color': '#2196F3',
      'target-arrow-color': '#2196F3',
    },
  },
  {
    selector: 'edge[type="registers_blueprint"]',
    style: {
      'line-style': 'dashed',
      'line-color': '#009688',
      'target-arrow-color': '#009688',
    },
  },
  {
    selector: 'edge[type="has_relationship"]',
    style: {
      'line-style': 'solid',
      'line-color': '#F44336',
      'target-arrow-color': '#F44336',
      'source-arrow-color': '#F44336',
      'source-arrow-shape': 'triangle',
    },
  },
  {
    selector: 'edge[type="uses_model"]',
    style: {
      'line-style': 'dotted',
      'line-color': '#9C27B0',
      'target-arrow-color': '#9C27B0',
    },
  },
  {
    selector: 'edge[type="dispatches_task"]',
    style: {
      'line-style': 'dashed',
      'line-color': '#FF9800',
      'target-arrow-color': '#FF9800',
    },
  },
];
