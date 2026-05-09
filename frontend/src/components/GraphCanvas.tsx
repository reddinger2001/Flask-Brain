import { useEffect, useRef, useState, useCallback } from 'react';
import cytoscape, { Core } from 'cytoscape';
import coseBilkent from 'cytoscape-cose-bilkent';
import { cytoscapeStyles, NODE_COLORS } from '../utils/cytoscapeStyles';
import { loadExpansion, saveExpansion } from '../utils/layoutStorage';
import type { Graph, Node, Manifest } from '../types/graph';

const TOGGLEABLE_TYPES = ['route', 'action', 'service', 'model', 'task'] as const;
type ToggleableType = typeof TOGGLEABLE_TYPES[number];

// Register layout
cytoscape.use(coseBilkent);

interface GraphCanvasProps {
  graph: Graph;
  onNodeSelect: (node: Node | null) => void;
  selectedNodeId: string | null;
  navigateTo?: Node | null;
  manifest?: Manifest | null;
}

interface Breadcrumb {
  type: 'all' | 'blueprint' | 'route';
  id?: string;
  label: string;
}

export function GraphCanvas({ graph, onNodeSelect, selectedNodeId, navigateTo, manifest }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const onNodeSelectRef = useRef(onNodeSelect);
  // Use refs for expanded state so click handlers always read the live value (no stale closure)
  const expandedBlueprintsRef = useRef<Set<string>>(new Set());
  const expandedRoutesRef = useRef<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');
  const [breadcrumbs, setBreadcrumbs] = useState<Breadcrumb[]>([{ type: 'all', label: 'All Blueprints' }]);
  const [hiddenTypes, setHiddenTypes] = useState<Set<ToggleableType>>(new Set());

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

  // Initialize Cytoscape with only blueprint nodes — depends only on graph, not callbacks
  useEffect(() => {
    if (!containerRef.current || !graph) return;

    // Get only blueprint nodes initially
    const blueprintNodes = graph.nodes.filter(n => n.type === 'blueprint');

    const cy = cytoscape({
      container: containerRef.current,
      elements: {
        nodes: blueprintNodes.map(node => ({
          data: {
            ...node,
          },
        })),
        edges: [], // No edges initially
      },
      style: [
        ...cytoscapeStyles,
        // Override node sizes for drill-down view
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
          selector: 'node[type="action"], node[type="service"], node[type="model"], node[type="task"]',
          style: {
            'width': '55px',
            'height': '55px',
            'font-size': '10px',
            'text-max-width': '50px',
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

  const handleNavigation = async (node: Node, targetNodeId?: string) => {
    const cy = cyRef.current;
    if (!cy) return;

    // If navigating to an action/service, remember it as the target
    const finalTargetId = targetNodeId || (node.type === 'action' || node.type === 'service' ? node.id : undefined);

    if (node.type === 'route') {
      // Find which blueprint owns this route (may be null for orphan/test routes)
      const bpEdge = graph.edges.find(e => e.target === node.id && e.type === 'registers_blueprint');
      const blueprintId = bpEdge?.source;
      const blueprintNode = blueprintId ? graph.nodes.find(n => n.id === blueprintId) : undefined;

      if (blueprintId && !expandedBlueprintsRef.current.has(blueprintId)) {
        // Expand blueprint first, then expand the route after layout settles
        const routeEdges = graph.edges.filter(
          e => e.source === blueprintId && e.type === 'registers_blueprint'
        );
        const routeIds = new Set(routeEdges.map(e => e.target));
        const routeChildren = graph.nodes.filter(n => routeIds.has(n.id));

        const toAdd: cytoscape.ElementDefinition[] = [];
        routeChildren.forEach(route => {
          if (!cy.getElementById(route.id).length) {
            toAdd.push({ group: 'nodes', data: { ...route } });
          }
        });
        routeEdges.forEach(edge => {
          const edgeId = `${edge.source}-${edge.target}`;
          if (!cy.getElementById(edgeId).length) {
            toAdd.push({ group: 'edges', data: { id: edgeId, source: edge.source, target: edge.target, type: edge.type } });
          }
        });
        if (toAdd.length) cy.add(toAdd);
        expandedBlueprintsRef.current.add(blueprintId);
        runLayout(cy);

        // Wait for layout to finish before expanding route
        cy.one('layoutstop', () => {
          expandRouteAndFinish(node.id, blueprintNode, finalTargetId);
        });
      } else {
        // No blueprint (orphan route) or blueprint already expanded — expand route directly
        expandRouteAndFinish(node.id, blueprintNode, finalTargetId);
      }
    } else if (node.type === 'action' || node.type === 'service') {
      // Find which route calls this node
      const callEdge = graph.edges.find(e => e.target === node.id && e.type === 'calls');
      if (!callEdge) {
        console.error('No route found for action/service:', node.id);
        return;
      }

      const sourceNode = graph.nodes.find(n => n.id === callEdge.source);
      if (sourceNode && sourceNode.type === 'route') {
        // Navigate to the route that calls this node, but remember the original target
        handleNavigation(sourceNode, node.id);
      } else {
        // Source might be another action — walk up the chain
        let currentId = callEdge.source;
        let routeNode: Node | undefined;
        const visited = new Set<string>();

        while (currentId && !visited.has(currentId)) {
          visited.add(currentId);
          const current = graph.nodes.find(n => n.id === currentId);
          if (current?.type === 'route') {
            routeNode = current;
            break;
          }
          const parentEdge = graph.edges.find(e => e.target === currentId && e.type === 'calls');
          currentId = parentEdge?.source || '';
        }

        if (routeNode) {
          handleNavigation(routeNode, node.id);
        } else {
          console.error('Could not find route for action/service:', node.id);
        }
      }
    }
  };

  const expandRouteAndFinish = async (routeId: string, blueprintNode: Node | undefined, targetNodeId?: string) => {
    const cy = cyRef.current;
    if (!cy) return;

    // Expand route if not already expanded
    if (!expandedRoutesRef.current.has(routeId)) {
      const safeId = routeId.replace('::', '_').replace(/\//g, '_').replace(/ /g, '_').replace(/</g, '').replace(/>/g, '').replace(/:/g, '_');
      try {
        const response = await fetch(`/api/graph/${safeId}`);
        if (!response.ok) {
          console.error(`Failed to fetch route subgraph: ${response.statusText}`);
          return;
        }

        const subgraph: Graph = await response.json();
        const toAdd: cytoscape.ElementDefinition[] = [];

        // Build set of all node IDs that will be present in cy after this add
        const existingNodeIds = new Set<string>(cy.nodes().map(n => n.id()));
        subgraph.nodes.forEach(node => {
          if (!cy.getElementById(node.id).length) {
            toAdd.push({ group: 'nodes', data: { ...node } });
            existingNodeIds.add(node.id);
          }
        });
        // Only add edges where both endpoints will exist (no dangling edges)
        subgraph.edges.forEach(edge => {
          const edgeId = `${edge.source}-${edge.target}`;
          if (!cy.getElementById(edgeId).length &&
              existingNodeIds.has(edge.source) &&
              existingNodeIds.has(edge.target)) {
            toAdd.push({ group: 'edges', data: { id: edgeId, source: edge.source, target: edge.target, type: edge.type } });
          }
        });

        if (toAdd.length) cy.add(toAdd);
        expandedRoutesRef.current.add(routeId);
        runLayout(cy);
      } catch (error) {
        console.error('Error fetching route subgraph:', error);
        return;
      }
    }

    // Update breadcrumbs
    const routeNode = graph.nodes.find(n => n.id === routeId);
    if (routeNode) {
      const newBreadcrumbs: Breadcrumb[] = [{ type: 'all', label: 'All Blueprints' }];
      if (blueprintNode) {
        newBreadcrumbs.push({ type: 'blueprint', id: blueprintNode.id, label: blueprintNode.label });
      }
      newBreadcrumbs.push({ type: 'route', id: routeId, label: routeNode.label });
      setBreadcrumbs(newBreadcrumbs);
    }

    // Select the target node (either the specified target or the route itself)
    const nodeIdToSelect = targetNodeId || routeId;
    onNodeSelectRef.current(graph.nodes.find(n => n.id === nodeIdToSelect) || null);

    // After a short delay for layout to settle, fit the viewport to the expanded route + its children
    setTimeout(() => {
      const cy = cyRef.current;
      if (!cy) return;
      const targetElem = cy.getElementById(nodeIdToSelect);
      const neighborhood = targetElem.closedNeighborhood();
      if (neighborhood.length > 0) {
        cy.fit(neighborhood, 80);
      } else {
        cy.fit(undefined, 50);
      }
      // Flash-highlight the target node so it's obvious
      cy.getElementById(nodeIdToSelect).addClass('selected');
    }, 500);
  };

  const runLayout = (cy: Core) => {
    cy.layout({
      name: 'cose-bilkent',
      animate: 'end' as any,
      animationDuration: 400,
      randomize: false,
      idealEdgeLength: 200,
      nodeRepulsion: 10000,
      padding: 60,
      nodeDimensionsIncludeLabels: true,
    } as any).run();
  };

  const handleNodeClick = (node: Node) => {
    if (node.type === 'blueprint') {
      toggleBlueprint(node.id);
    } else if (node.type === 'route') {
      toggleRoute(node.id);
    }
  };

  const toggleBlueprint = (blueprintId: string) => {
    const cy = cyRef.current;
    if (!cy) return;

    const isExpanded = expandedBlueprintsRef.current.has(blueprintId);

    const routeEdges = graph.edges.filter(
      e => e.source === blueprintId && e.type === 'registers_blueprint'
    );
    const routeIds = new Set(routeEdges.map(e => e.target));
    const routeChildren = graph.nodes.filter(n => routeIds.has(n.id));

    if (isExpanded) {
      routeChildren.forEach(route => {
        if (expandedRoutesRef.current.has(route.id)) collapseRoute(route.id);
        cy.getElementById(route.id).remove();
      });
      cy.edges().forEach(edge => {
        if (routeIds.has(edge.data('source')) || routeIds.has(edge.data('target'))) {
          edge.remove();
        }
      });
      expandedBlueprintsRef.current.delete(blueprintId);
      setBreadcrumbs([{ type: 'all', label: 'All Blueprints' }]);
    } else {
      const toAdd: cytoscape.ElementDefinition[] = [];
      routeChildren.forEach(route => {
        if (!cy.getElementById(route.id).length) {
          toAdd.push({ group: 'nodes', data: { ...route } });
        }
      });
      routeEdges.forEach(edge => {
        const edgeId = `${edge.source}-${edge.target}`;
        if (!cy.getElementById(edgeId).length) {
          toAdd.push({ group: 'edges', data: { id: edgeId, source: edge.source, target: edge.target, type: edge.type } });
        }
      });
      if (toAdd.length) cy.add(toAdd);
      expandedBlueprintsRef.current.add(blueprintId);

      const blueprintNode = graph.nodes.find(n => n.id === blueprintId);
      if (blueprintNode) {
        setBreadcrumbs([
          { type: 'all', label: 'All Blueprints' },
          { type: 'blueprint', id: blueprintId, label: blueprintNode.label },
        ]);
      }
    }

    runLayout(cy);
    persistCurrentExpansion();
  };

  const toggleRoute = async (routeId: string) => {
    const cy = cyRef.current;
    if (!cy) return;

    const isExpanded = expandedRoutesRef.current.has(routeId);

    if (isExpanded) {
      collapseRoute(routeId);
    } else {
      const safeId = routeId.replace('::', '_').replace(/\//g, '_').replace(/ /g, '_').replace(/</g, '').replace(/>/g, '').replace(/:/g, '_');
      try {
        const response = await fetch(`/api/graph/${safeId}`);
        if (!response.ok) {
          console.error(`Failed to fetch route subgraph: ${response.statusText}`);
          return;
        }

        const subgraph: Graph = await response.json();
        const toAdd: cytoscape.ElementDefinition[] = [];

        const existingNodeIds2 = new Set<string>(cy.nodes().map(n => n.id()));
        subgraph.nodes.forEach(node => {
          if (node.id !== routeId && !cy.getElementById(node.id).length) {
            toAdd.push({ group: 'nodes', data: { ...node } });
            existingNodeIds2.add(node.id);
          }
        });
        subgraph.edges.forEach(edge => {
          const edgeId = `${edge.source}-${edge.target}`;
          if (!cy.getElementById(edgeId).length &&
              existingNodeIds2.has(edge.source) &&
              existingNodeIds2.has(edge.target)) {
            toAdd.push({ group: 'edges', data: { id: edgeId, source: edge.source, target: edge.target, type: edge.type } });
          }
        });

        if (toAdd.length) cy.add(toAdd);
        expandedRoutesRef.current.add(routeId);

        // Breadcrumb — look up blueprint via edges since metadata.blueprint is a name not an ID
        const routeNode = graph.nodes.find(n => n.id === routeId);
        const bpEdge = graph.edges.find(e => e.target === routeId && e.type === 'registers_blueprint');
        const blueprintNode = bpEdge ? graph.nodes.find(n => n.id === bpEdge.source) : null;

        if (routeNode) {
          const newBreadcrumbs: Breadcrumb[] = [{ type: 'all', label: 'All Blueprints' }];
          if (blueprintNode) {
            newBreadcrumbs.push({ type: 'blueprint', id: blueprintNode.id, label: blueprintNode.label });
          }
          newBreadcrumbs.push({ type: 'route', id: routeId, label: routeNode.label });
          setBreadcrumbs(newBreadcrumbs);
        }

        runLayout(cy);
        persistCurrentExpansion();
      } catch (error) {
        console.error('Error fetching route subgraph:', error);
      }
    }
  };

  const collapseRoute = (routeId: string) => {
    const cy = cyRef.current;
    if (!cy) return;

    const connectedNodes = cy.getElementById(routeId).neighborhood('node');
    connectedNodes.forEach(node => {
      const nodeType = node.data('type');
      if (['action', 'service', 'model', 'task'].includes(nodeType)) {
        node.remove();
      }
    });

    expandedRoutesRef.current.delete(routeId);

    const bpEdge = graph.edges.find(e => e.target === routeId && e.type === 'registers_blueprint');
    const blueprintNode = bpEdge ? graph.nodes.find(n => n.id === bpEdge.source) : null;

    if (blueprintNode && expandedBlueprintsRef.current.has(blueprintNode.id)) {
      setBreadcrumbs([
        { type: 'all', label: 'All Blueprints' },
        { type: 'blueprint', id: blueprintNode.id, label: blueprintNode.label },
      ]);
    } else {
      setBreadcrumbs([{ type: 'all', label: 'All Blueprints' }]);
    }

    runLayout(cy);
    persistCurrentExpansion();
  };

  const collapseAll = () => {
    const cy = cyRef.current;
    if (!cy) return;

    cy.nodes().forEach(node => {
      if (node.data('type') !== 'blueprint') node.remove();
    });

    expandedBlueprintsRef.current.clear();
    expandedRoutesRef.current.clear();
    setBreadcrumbs([{ type: 'all', label: 'All Blueprints' }]);

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
      {/* Breadcrumb */}
      <div className="absolute top-4 left-4 z-10 bg-white dark:bg-gray-800 rounded-lg shadow-lg px-4 py-2">
        <div className="flex items-center gap-2 text-sm">
          {breadcrumbs.map((crumb, index) => (
            <div key={index} className="flex items-center gap-2">
              {index > 0 && (
                <svg className="h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              )}
              <span className={index === breadcrumbs.length - 1 ? 'font-semibold text-gray-900 dark:text-white' : 'text-gray-600 dark:text-gray-400'}>
                {crumb.label}
              </span>
            </div>
          ))}
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
                  className="px-2 py-0.5 rounded-full text-xs font-semibold border transition-all"
                  style={{
                    backgroundColor: hidden ? 'transparent' : (NODE_COLORS as any)[type] + '33',
                    borderColor: (NODE_COLORS as any)[type],
                    color: hidden ? '#888' : (NODE_COLORS as any)[type],
                    textDecoration: hidden ? 'line-through' : 'none',
                    opacity: hidden ? 0.5 : 1,
                  }}
                  title={hidden ? `Show ${type}s` : `Hide ${type}s`}
                >
                  {type}
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

          <button
            onClick={handleReset}
            className="px-3 py-2 bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 border border-gray-300 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white transition-colors"
            title="Reset to blueprints"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
      </div>

      {/* Canvas */}
      <div ref={containerRef} className="w-full h-full bg-gray-50 dark:bg-gray-900" />
    </div>
  );
}
