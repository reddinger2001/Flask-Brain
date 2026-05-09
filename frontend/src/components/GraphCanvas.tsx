import { useEffect, useRef, useState, useCallback } from 'react';
import cytoscape, { Core } from 'cytoscape';
import coseBilkent from 'cytoscape-cose-bilkent';
import dagre from 'cytoscape-dagre';
import { cytoscapeStyles, NODE_COLORS } from '../utils/cytoscapeStyles';
import { loadExpansion, saveExpansion } from '../utils/layoutStorage';
import type { Graph, Node, Manifest } from '../types/graph';

const TOGGLEABLE_TYPES = ['route', 'action', 'service', 'model', 'task'] as const;
type ToggleableType = typeof TOGGLEABLE_TYPES[number];

// Rank mapping for hierarchical layout
const RANK_MAP: Record<string, number> = {
  blueprint: 0,
  route: 1,
  action: 2,
  service: 2,
  task: 2,
  model: 3,
};

// Register layouts
cytoscape.use(coseBilkent);
cytoscape.use(dagre);

interface GraphCanvasProps {
  graph: Graph;
  onNodeSelect: (node: Node | null) => void;
  selectedNodeId: string | null;
  navigateTo?: Node | null;
  manifest?: Manifest | null;
}

export function GraphCanvas({ graph, onNodeSelect, selectedNodeId, navigateTo, manifest }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const onNodeSelectRef = useRef(onNodeSelect);
  
  // Use refs for all expanded state to avoid stale closures in Cytoscape click handlers
  const expandedModelsRef = useRef<Set<string>>(new Set());
  const expandedActionsRef = useRef<Set<string>>(new Set());
  const expandedRoutesRef = useRef<Set<string>>(new Set());
  const expandedBlueprintsRef = useRef<Set<string>>(new Set());
  
  const [searchQuery, setSearchQuery] = useState('');
  const [hiddenTypes, setHiddenTypes] = useState<Set<ToggleableType>>(new Set());
  const [blueprintList, setBlueprintList] = useState<Array<{ id: string; label: string }>>([]);

  // Keep callback ref stable so the Cytoscape init effect doesn't re-run on every render
  useEffect(() => { onNodeSelectRef.current = onNodeSelect; }, [onNodeSelect]);

  // Persist current expansion state to localStorage whenever it changes
  const persistCurrentExpansion = useCallback(() => {
    if (!manifest?.scan_timestamp) return;
    saveExpansion(manifest.scan_timestamp, {
      blueprints: [...expandedBlueprintsRef.current],
      routes: [...expandedRoutesRef.current],
    });
  }, [manifest?.scan_timestamp]);

  // Initialize Cytoscape with only model nodes and has_relationship edges
  useEffect(() => {
    if (!containerRef.current || !graph) return;

    // Get only model nodes initially
    const modelNodes = graph.nodes.filter(n => n.type === 'model');
    
    // Get has_relationship edges between models
    const modelIds = new Set(modelNodes.map(n => n.id));
    const modelEdges = graph.edges.filter(
      e => e.type === 'has_relationship' && modelIds.has(e.source) && modelIds.has(e.target)
    );

    // Build blueprint list for the left panel
    const blueprints = graph.nodes
      .filter(n => n.type === 'blueprint')
      .map(n => ({ id: n.id, label: n.label }))
      .sort((a, b) => a.label.localeCompare(b.label));
    setBlueprintList(blueprints);

    const cy = cytoscape({
      container: containerRef.current,
      elements: {
        nodes: modelNodes.map(node => ({
          data: {
            ...node,
            rank: RANK_MAP[node.type] ?? 2,
          },
        })),
        edges: modelEdges.map(edge => ({
          data: {
            id: `${edge.source}-${edge.target}`,
            source: edge.source,
            target: edge.target,
            type: edge.type,
          },
        })),
      },
      style: [
        ...cytoscapeStyles,
        // Override node sizes for drill-down view
        {
          selector: 'node[type="model"]',
          style: {
            'width': '70px',
            'height': '70px',
            'font-size': '11px',
            'text-max-width': '60px',
          },
        },
        {
          selector: 'node[type="action"], node[type="service"], node[type="task"]',
          style: {
            'width': '55px',
            'height': '55px',
            'font-size': '10px',
            'text-max-width': '50px',
          },
        },
        {
          selector: 'node[type="route"]',
          style: {
            'width': '70px',
            'height': '70px',
            'font-size': '11px',
            'text-max-width': '60px',
          },
        },
        {
          selector: 'node[type="blueprint"]',
          style: {
            'width': '100px',
            'height': '100px',
            'font-size': '14px',
            'font-weight': 'bold',
            'text-max-width': '90px',
          },
        },
      ],
      minZoom: 0.1,
      maxZoom: 3,
      wheelSensitivity: 0.2,
    });

    cyRef.current = cy;

    // Apply initial layout
    runLayout(cy);

    // Restore persisted expansion after the initial layout settles
    cy.one('layoutstop', () => {
      if (!manifest?.scan_timestamp) return;
      const persisted = loadExpansion(manifest.scan_timestamp);
      if (!persisted) return;
      // Re-expand saved blueprints
      persisted.blueprints.forEach(bpId => {
        if (graph.nodes.some(n => n.id === bpId)) {
          toggleBlueprint(bpId);
        }
      });
    });

    // Handle node clicks
    cy.on('tap', 'node', (event) => {
      const node = event.target.data() as Node;
      onNodeSelectRef.current(node);
      handleNodeClick(node);
    });

    // Handle background tap — just deselect, don't collapse
    cy.on('tap', (event) => {
      if (event.target === cy) {
        onNodeSelectRef.current(null);
      }
    });

    // Handle node hover — tooltip scoped to container, always cleaned up
    let activeTooltip: HTMLDivElement | null = null;
    let activeMouseMove: ((e: MouseEvent) => void) | null = null;

    const removeTooltip = () => {
      if (activeTooltip) { activeTooltip.remove(); activeTooltip = null; }
      if (activeMouseMove) { document.removeEventListener('mousemove', activeMouseMove); activeMouseMove = null; }
    };

    cy.on('mouseover', 'node', (event) => {
      removeTooltip(); // clean up any stale tooltip first
      const node = event.target.data() as Node;
      const tooltip = document.createElement('div');
      tooltip.className = 'fixed bg-gray-900 text-white px-3 py-2 rounded-lg text-sm shadow-lg z-50 pointer-events-none';
      tooltip.innerHTML = `<div class="font-semibold">${node.label}</div><div class="text-gray-300 text-xs mt-1">${node.file_path}:${node.line_number}</div>`;
      document.body.appendChild(tooltip);
      activeTooltip = tooltip;

      activeMouseMove = (e: MouseEvent) => {
        tooltip.style.left = `${e.clientX + 14}px`;
        tooltip.style.top = `${e.clientY + 14}px`;
      };
      document.addEventListener('mousemove', activeMouseMove);
    });

    cy.on('mouseout', 'node', () => removeTooltip());

    // Also kill tooltip if mouse leaves the canvas container entirely
    containerRef.current?.addEventListener('mouseleave', removeTooltip);

    return () => {
      removeTooltip();
      cy.destroy();
    };
  }, [graph]); // onNodeSelect intentionally omitted — stored in ref to prevent Cytoscape re-init

  // Update selected node styling
  useEffect(() => {
    if (!cyRef.current) return;
    
    cyRef.current.nodes().removeClass('selected');
    if (selectedNodeId) {
      cyRef.current.getElementById(selectedNodeId).addClass('selected');
    }
  }, [selectedNodeId]);

  // Handle search/highlight
  useEffect(() => {
    if (!cyRef.current) return;

    const cy = cyRef.current;
    
    if (!searchQuery.trim()) {
      // Reset all nodes to full opacity
      cy.nodes().style('opacity', 1);
      cy.edges().style('opacity', 1);
    } else {
      const query = searchQuery.toLowerCase();
      
      cy.nodes().forEach((node) => {
        const label = node.data('label') as string;
        if (label.toLowerCase().includes(query)) {
          node.style('opacity', 1);
        } else {
          node.style('opacity', 0.15);
        }
      });

      // Dim edges connected to dimmed nodes
      cy.edges().forEach((edge) => {
        const source = edge.source();
        const target = edge.target();
        const sourceOpacity = parseFloat(source.style('opacity'));
        const targetOpacity = parseFloat(target.style('opacity'));
        
        // Edge is visible if both nodes are visible
        if (sourceOpacity === 1 && targetOpacity === 1) {
          edge.style('opacity', 1);
        } else {
          edge.style('opacity', 0.15);
        }
      });
    }
  }, [searchQuery]);

  // Handle node type visibility toggling
  useEffect(() => {
    if (!cyRef.current) return;
    const cy = cyRef.current;
    TOGGLEABLE_TYPES.forEach(type => {
      cy.nodes(`[type="${type}"]`).style('display', hiddenTypes.has(type) ? 'none' : 'element');
    });
    // Hide edges where either endpoint is hidden
    cy.edges().forEach(edge => {
      const srcHidden = edge.source().style('display') === 'none';
      const tgtHidden = edge.target().style('display') === 'none';
      edge.style('display', srcHidden || tgtHidden ? 'none' : 'element');
    });
  }, [hiddenTypes]);

  // Handle navigation from other tabs (RouteMap, Heatmap)
  useEffect(() => {
    if (!navigateTo) return;

    // Wait for cyRef to be ready (in case we just switched tabs)
    let attempts = 0;
    const maxAttempts = 10;
    const pollInterval = 50;

    const waitForCy = () => {
      if (cyRef.current) {
        handleNavigation(navigateTo);
      } else if (attempts < maxAttempts) {
        attempts++;
        setTimeout(waitForCy, pollInterval);
      } else {
        console.error('GraphCanvas: cyRef not ready after navigation');
      }
    };

    waitForCy();
  }, [navigateTo]);

  const handleNavigation = async (node: Node) => {
    const cy = cyRef.current;
    if (!cy) return;

    if (node.type === 'model') {
      // Model is already visible — just select it
      onNodeSelectRef.current(node);
      cy.getElementById(node.id).addClass('selected');
      cy.fit(cy.getElementById(node.id).closedNeighborhood(), 80);
    } else if (node.type === 'action' || node.type === 'service') {
      // Find which model this action uses via uses_model edge
      const usesModelEdge = graph.edges.find(e => e.source === node.id && e.type === 'uses_model');
      if (usesModelEdge) {
        const modelNode = graph.nodes.find(n => n.id === usesModelEdge.target);
        if (modelNode) {
          // Expand the model to show the action
          if (!expandedModelsRef.current.has(modelNode.id)) {
            await toggleModel(modelNode.id);
          }
          // Now select the action
          onNodeSelectRef.current(node);
          cy.getElementById(node.id).addClass('selected');
          cy.fit(cy.getElementById(node.id).closedNeighborhood(), 80);
        }
      }
    } else if (node.type === 'route') {
      // Find which action this route calls via calls edge
      const callsEdge = graph.edges.find(e => e.source === node.id && e.type === 'calls');
      if (callsEdge) {
        const actionNode = graph.nodes.find(n => n.id === callsEdge.target);
        if (actionNode) {
          // Navigate to the action first, which will expand the model
          await handleNavigation(actionNode);
          // Then expand the action to show the route
          if (!expandedActionsRef.current.has(actionNode.id)) {
            await toggleAction(actionNode.id);
          }
          // Now select the route
          onNodeSelectRef.current(node);
          cy.getElementById(node.id).addClass('selected');
          cy.fit(cy.getElementById(node.id).closedNeighborhood(), 80);
        }
      }
    }
  };

  const runLayout = (cy: Core) => {
    cy.layout({
      name: 'dagre',
      rankDir: 'TB',          // Top → Bottom
      align: 'UL',
      nodeSep: 60,
      rankSep: 120,
      padding: 60,
      animate: true,
      animationDuration: 400,
      fit: true,
    } as any).run();
  };

  const handleNodeClick = (node: Node) => {
    if (node.type === 'model') {
      toggleModel(node.id);
    } else if (node.type === 'action' || node.type === 'service') {
      toggleAction(node.id);
    } else if (node.type === 'route') {
      toggleRoute(node.id);
    }
  };

  const toggleModel = async (modelId: string) => {
    const cy = cyRef.current;
    if (!cy) return;

    const isExpanded = expandedModelsRef.current.has(modelId);

    if (isExpanded) {
      // Collapse: remove all actions connected via uses_model
      const usesModelEdges = graph.edges.filter(
        e => e.target === modelId && e.type === 'uses_model'
      );
      const actionIds = new Set(usesModelEdges.map(e => e.source));
      
      // First collapse any expanded actions
      actionIds.forEach(actionId => {
        if (expandedActionsRef.current.has(actionId)) {
          collapseAction(actionId);
        }
      });

      // Remove action nodes and edges
      actionIds.forEach(actionId => {
        cy.getElementById(actionId).remove();
      });
      cy.edges().forEach(edge => {
        if (actionIds.has(edge.data('source')) || actionIds.has(edge.data('target'))) {
          edge.remove();
        }
      });

      expandedModelsRef.current.delete(modelId);
    } else {
      // Expand: add all actions connected via uses_model
      const usesModelEdges = graph.edges.filter(
        e => e.target === modelId && e.type === 'uses_model'
      );
      const actionIds = new Set(usesModelEdges.map(e => e.source));
      const actionNodes = graph.nodes.filter(n => actionIds.has(n.id));

      const toAdd: cytoscape.ElementDefinition[] = [];
      actionNodes.forEach(action => {
        if (!cy.getElementById(action.id).length) {
          toAdd.push({ group: 'nodes', data: { ...action, rank: RANK_MAP[action.type] ?? 2 } });
        }
      });
      usesModelEdges.forEach(edge => {
        const edgeId = `${edge.source}-${edge.target}`;
        if (!cy.getElementById(edgeId).length &&
            cy.getElementById(edge.source).length &&
            cy.getElementById(edge.target).length) {
          toAdd.push({ group: 'edges', data: { id: edgeId, source: edge.source, target: edge.target, type: edge.type } });
        }
      });
      if (toAdd.length) cy.add(toAdd);
      expandedModelsRef.current.add(modelId);
    }

    runLayout(cy);
    persistCurrentExpansion();
  };

  const toggleAction = async (actionId: string) => {
    const cy = cyRef.current;
    if (!cy) return;

    const isExpanded = expandedActionsRef.current.has(actionId);

    if (isExpanded) {
      collapseAction(actionId);
    } else {
      // Expand: add all routes connected via calls
      const callsEdges = graph.edges.filter(
        e => e.target === actionId && e.type === 'calls'
      );
      const routeIds = new Set(callsEdges.map(e => e.source));
      const routeNodes = graph.nodes.filter(n => routeIds.has(n.id));

      const toAdd: cytoscape.ElementDefinition[] = [];
      routeNodes.forEach(route => {
        if (!cy.getElementById(route.id).length) {
          toAdd.push({ group: 'nodes', data: { ...route, rank: RANK_MAP[route.type] ?? 2 } });
        }
      });
      callsEdges.forEach(edge => {
        const edgeId = `${edge.source}-${edge.target}`;
        if (!cy.getElementById(edgeId).length &&
            cy.getElementById(edge.source).length &&
            cy.getElementById(edge.target).length) {
          toAdd.push({ group: 'edges', data: { id: edgeId, source: edge.source, target: edge.target, type: edge.type } });
        }
      });
      if (toAdd.length) cy.add(toAdd);
      expandedActionsRef.current.add(actionId);
    }

    runLayout(cy);
    persistCurrentExpansion();
  };

  const collapseAction = (actionId: string) => {
    const cy = cyRef.current;
    if (!cy) return;

    // Remove all routes connected to this action
    const callsEdges = graph.edges.filter(
      e => e.target === actionId && e.type === 'calls'
    );
    const routeIds = new Set(callsEdges.map(e => e.source));

    // First collapse any expanded routes
    routeIds.forEach(routeId => {
      if (expandedRoutesRef.current.has(routeId)) {
        collapseRoute(routeId);
      }
    });

    // Remove route nodes and edges
    routeIds.forEach(routeId => {
      cy.getElementById(routeId).remove();
    });
    cy.edges().forEach(edge => {
      if (routeIds.has(edge.data('source')) || routeIds.has(edge.data('target'))) {
        edge.remove();
      }
    });

    expandedActionsRef.current.delete(actionId);
  };

  const toggleRoute = async (routeId: string) => {
    const cy = cyRef.current;
    if (!cy) return;

    const isExpanded = expandedRoutesRef.current.has(routeId);

    if (isExpanded) {
      collapseRoute(routeId);
    } else {
      // Expand: add the blueprint that registers this route
      const registersBlueprintEdge = graph.edges.find(
        e => e.target === routeId && e.type === 'registers_blueprint'
      );
      if (registersBlueprintEdge) {
        const blueprintNode = graph.nodes.find(n => n.id === registersBlueprintEdge.source);
        if (blueprintNode) {
          const toAdd: cytoscape.ElementDefinition[] = [];
          if (!cy.getElementById(blueprintNode.id).length) {
            toAdd.push({ group: 'nodes', data: { ...blueprintNode } });
          }
          const edgeId = `${registersBlueprintEdge.source}-${registersBlueprintEdge.target}`;
          if (!cy.getElementById(edgeId).length &&
              cy.getElementById(registersBlueprintEdge.source).length &&
              cy.getElementById(registersBlueprintEdge.target).length) {
            toAdd.push({ 
              group: 'edges', 
              data: { 
                id: edgeId, 
                source: registersBlueprintEdge.source, 
                target: registersBlueprintEdge.target, 
                type: registersBlueprintEdge.type 
              } 
            });
          }
          if (toAdd.length) cy.add(toAdd);
          expandedRoutesRef.current.add(routeId);
        }
      }
    }

    runLayout(cy);
    persistCurrentExpansion();
  };

  const collapseRoute = (routeId: string) => {
    const cy = cyRef.current;
    if (!cy) return;

    // Remove the blueprint connected to this route
    const registersBlueprintEdge = graph.edges.find(
      e => e.target === routeId && e.type === 'registers_blueprint'
    );
    if (registersBlueprintEdge) {
      const blueprintId = registersBlueprintEdge.source;
      // Only remove the blueprint if no other expanded routes reference it
      const otherExpandedRoutes = [...expandedRoutesRef.current].filter(rid => rid !== routeId);
      const otherRoutesBlueprintEdges = graph.edges.filter(
        e => e.type === 'registers_blueprint' && 
             e.source === blueprintId && 
             otherExpandedRoutes.includes(e.target)
      );
      if (otherRoutesBlueprintEdges.length === 0) {
        cy.getElementById(blueprintId).remove();
        cy.edges().forEach(edge => {
          if (edge.data('source') === blueprintId || edge.data('target') === blueprintId) {
            edge.remove();
          }
        });
      }
    }

    expandedRoutesRef.current.delete(routeId);
  };

  const toggleBlueprint = (blueprintId: string) => {
    const cy = cyRef.current;
    if (!cy) return;

    const isExpanded = expandedBlueprintsRef.current.has(blueprintId);

    if (isExpanded) {
      // Collapse: remove all routes registered by this blueprint
      const registersBlueprintEdges = graph.edges.filter(
        e => e.source === blueprintId && e.type === 'registers_blueprint'
      );
      const routeIds = new Set(registersBlueprintEdges.map(e => e.target));

      // First collapse any expanded routes
      routeIds.forEach(routeId => {
        if (expandedRoutesRef.current.has(routeId)) {
          collapseRoute(routeId);
        }
      });

      // Remove route nodes and edges
      routeIds.forEach(routeId => {
        cy.getElementById(routeId).remove();
      });
      cy.edges().forEach(edge => {
        if (routeIds.has(edge.data('source')) || routeIds.has(edge.data('target'))) {
          edge.remove();
        }
      });

      // Remove the blueprint node itself
      cy.getElementById(blueprintId).remove();

      expandedBlueprintsRef.current.delete(blueprintId);
    } else {
      // Expand: add the blueprint and all its routes
      const blueprintNode = graph.nodes.find(n => n.id === blueprintId);
      if (!blueprintNode) return;

      const registersBlueprintEdges = graph.edges.filter(
        e => e.source === blueprintId && e.type === 'registers_blueprint'
      );
      const routeIds = new Set(registersBlueprintEdges.map(e => e.target));
      const routeNodes = graph.nodes.filter(n => routeIds.has(n.id));

      const toAdd: cytoscape.ElementDefinition[] = [];
      
      // Add blueprint node
      if (!cy.getElementById(blueprintNode.id).length) {
        toAdd.push({ group: 'nodes', data: { ...blueprintNode, rank: RANK_MAP[blueprintNode.type] ?? 2 } });
      }

      // Add route nodes
      routeNodes.forEach(route => {
        if (!cy.getElementById(route.id).length) {
          toAdd.push({ group: 'nodes', data: { ...route, rank: RANK_MAP[route.type] ?? 2 } });
        }
      });

      // Add edges (only if both endpoints exist)
      registersBlueprintEdges.forEach(edge => {
        const edgeId = `${edge.source}-${edge.target}`;
        if (!cy.getElementById(edgeId).length) {
          toAdd.push({ 
            group: 'edges', 
            data: { 
              id: edgeId, 
              source: edge.source, 
              target: edge.target, 
              type: edge.type 
            } 
          });
        }
      });

      if (toAdd.length) cy.add(toAdd);
      expandedBlueprintsRef.current.add(blueprintId);
    }

    runLayout(cy);
    persistCurrentExpansion();
  };

  const collapseAll = () => {
    const cy = cyRef.current;
    if (!cy) return;

    // Remove all non-model nodes
    cy.nodes().forEach(node => {
      if (node.data('type') !== 'model') node.remove();
    });

    // Remove all non-has_relationship edges
    cy.edges().forEach(edge => {
      if (edge.data('type') !== 'has_relationship') edge.remove();
    });

    expandedModelsRef.current.clear();
    expandedActionsRef.current.clear();
    expandedRoutesRef.current.clear();
    expandedBlueprintsRef.current.clear();

    runLayout(cy);
  };

  const handleFit = () => {
    if (cyRef.current) cyRef.current.fit(undefined, 50);
  };

  const handleReset = () => {
    collapseAll();
    onNodeSelectRef.current(null);
  };

  return (
    <div className="relative w-full h-full">
      {/* Blueprint panel (left side) */}
      <div className="absolute top-4 left-4 z-10 bg-white dark:bg-gray-800 rounded-lg shadow-lg p-4" style={{ maxWidth: '250px' }}>
        {/* Reset button */}
        <button
          onClick={handleReset}
          className="w-full mb-3 px-3 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg text-sm font-medium transition-colors"
          title="Reset to models only"
        >
          Reset
        </button>

        {/* Blueprint list */}
        <div className="border-t border-gray-200 dark:border-gray-700 pt-3">
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-2 font-medium uppercase tracking-wide">
            Blueprints
          </p>
          <div className="flex flex-col gap-1.5 overflow-y-auto" style={{ maxHeight: '60vh' }}>
            {blueprintList.map(bp => {
              const isOverlaid = expandedBlueprintsRef.current.has(bp.id);
              return (
                <button
                  key={bp.id}
                  onClick={() => toggleBlueprint(bp.id)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all text-left ${
                    isOverlaid
                      ? 'bg-teal-600 text-white'
                      : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                  }`}
                  title={isOverlaid ? `Hide ${bp.label}` : `Show ${bp.label}`}
                >
                  {bp.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="absolute top-4 right-4 z-10 flex flex-col gap-2">
        {/* Search */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-2">
          <div className="relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search nodes..."
              className="w-64 px-3 py-2 pl-9 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
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
        </div>

        {/* Node type filter chips */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-2">
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1.5 font-medium uppercase tracking-wide">Show / Hide</p>
          <div className="flex flex-wrap gap-1">
            {TOGGLEABLE_TYPES.map(type => {
              const hidden = hiddenTypes.has(type);
              return (
                <button
                  key={type}
                  onClick={() => setHiddenTypes(prev => {
                    const next = new Set(prev);
                    if (next.has(type)) next.delete(type); else next.add(type);
                    return next;
                  })}
                  className="px-2 py-1 rounded-full text-xs font-bold border-2 transition-all select-none"
                  style={hidden ? {
                    backgroundColor: '#374151',
                    borderColor: '#4B5563',
                    color: '#6B7280',
                    textDecoration: 'line-through',
                  } : {
                    backgroundColor: (NODE_COLORS as any)[type],
                    borderColor: (NODE_COLORS as any)[type],
                    color: '#fff',
                  }}
                  title={hidden ? `Show ${type}s` : `Hide ${type}s`}
                >
                  {hidden ? '✕ ' : '● '}{type}
                </button>
              );
            })}
          </div>
        </div>

        {/* Buttons */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-2 flex gap-2">
          <button
            onClick={handleFit}
            className="px-3 py-2 bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 border border-gray-300 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white transition-colors"
            title="Fit to view"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
            </svg>
          </button>
        </div>
      </div>

      {/* Canvas */}
      <div ref={containerRef} className="w-full h-full bg-gray-50 dark:bg-gray-900" />
    </div>
  );
}
