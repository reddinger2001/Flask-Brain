import React, { useState, useMemo, useRef } from 'react';
import { Graph, Node } from '../types/graph';

interface ClassDiagramProps {
  graph: Graph;
  onNodeSelect: (node: Node | null) => void;
  selectedNodeId: string | null;
}

interface ClassBox {
  node: Node;
  x: number;
  y: number;
  width: number;
  height: number;
}

interface Point {
  x: number;
  y: number;
}

const ClassDiagram: React.FC<ClassDiagramProps> = ({ graph, onNodeSelect, selectedNodeId }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [hideIsolated, setHideIsolated] = useState(false);
  const [zoom, setZoom] = useState(1);
  const svgRef = useRef<SVGSVGElement>(null);

  // Filter model nodes
  const modelNodes = useMemo(() => {
    return graph.nodes.filter(node => node.type === 'model');
  }, [graph.nodes]);

  // Get relationship edges
  const relationshipEdges = useMemo(() => {
    return graph.edges.filter(edge => edge.type === 'has_relationship');
  }, [graph.edges]);

  // Build set of nodes that have relationships
  const connectedNodeIds = useMemo(() => {
    const ids = new Set<string>();
    relationshipEdges.forEach(edge => {
      // Skip self-referential edges
      if (edge.source !== edge.target) {
        ids.add(edge.source);
        ids.add(edge.target);
      }
    });
    return ids;
  }, [relationshipEdges]);

  // Filter visible nodes based on search and isolation toggle
  const visibleNodes = useMemo(() => {
    return modelNodes.filter(node => {
      // Search filter
      if (searchTerm && !node.label.toLowerCase().includes(searchTerm.toLowerCase())) {
        return false;
      }
      // Isolation filter
      if (hideIsolated && !connectedNodeIds.has(node.id)) {
        return false;
      }
      return true;
    });
  }, [modelNodes, searchTerm, hideIsolated, connectedNodeIds]);

  // Calculate layout
  const classBoxes = useMemo(() => {
    const boxes: ClassBox[] = [];
    const nodeCount = visibleNodes.length;
    
    if (nodeCount === 0) return boxes;

    const cols = Math.ceil(Math.sqrt(nodeCount));
    const boxWidth = 200;
    const horizontalSpacing = 80;
    const verticalSpacing = 100;

    visibleNodes.forEach((node, index) => {
      const col = index % cols;
      const row = Math.floor(index / cols);
      
      // Calculate box height based on attributes
      const columns = node.metadata.columns || {};
      const columnEntries = Object.entries(columns);
      const displayedColumns = columnEntries.slice(0, 8);
      const hasMore = columnEntries.length > 8;
      
      const headerHeight = 50;
      const attributeRowHeight = 20;
      const attributesHeight = displayedColumns.length > 0 
        ? displayedColumns.length * attributeRowHeight + (hasMore ? attributeRowHeight : 0)
        : attributeRowHeight; // "(no columns)" row
      const methodsHeight = 30; // minimal methods section
      const boxHeight = Math.max(120, headerHeight + attributesHeight + methodsHeight);

      boxes.push({
        node,
        x: col * (boxWidth + horizontalSpacing) + 50,
        y: row * (boxHeight + verticalSpacing) + 50,
        width: boxWidth,
        height: boxHeight,
      });
    });

    return boxes;
  }, [visibleNodes]);

  // Calculate SVG dimensions
  const svgDimensions = useMemo(() => {
    if (classBoxes.length === 0) {
      return { width: 800, height: 600 };
    }

    const maxX = Math.max(...classBoxes.map(b => b.x + b.width));
    const maxY = Math.max(...classBoxes.map(b => b.y + b.height));

    return {
      width: maxX + 50,
      height: maxY + 50,
    };
  }, [classBoxes]);

  // Build node ID to box map for edge rendering
  const nodeIdToBox = useMemo(() => {
    const map = new Map<string, ClassBox>();
    classBoxes.forEach(box => map.set(box.node.id, box));
    return map;
  }, [classBoxes]);

  // Filter visible edges
  const visibleEdges = useMemo(() => {
    return relationshipEdges.filter(edge => {
      // Skip self-referential
      if (edge.source === edge.target) return false;
      // Both nodes must be visible
      return nodeIdToBox.has(edge.source) && nodeIdToBox.has(edge.target);
    });
  }, [relationshipEdges, nodeIdToBox]);

  // Calculate edge paths
  const edgePaths = useMemo(() => {
    return visibleEdges.map(edge => {
      const sourceBox = nodeIdToBox.get(edge.source)!;
      const targetBox = nodeIdToBox.get(edge.target)!;

      // Start from center-right of source
      const start: Point = {
        x: sourceBox.x + sourceBox.width,
        y: sourceBox.y + sourceBox.height / 2,
      };

      // End at center-left of target
      const end: Point = {
        x: targetBox.x,
        y: targetBox.y + targetBox.height / 2,
      };

      // Calculate midpoint for label
      const midpoint: Point = {
        x: (start.x + end.x) / 2,
        y: (start.y + end.y) / 2,
      };

      return {
        edge,
        start,
        end,
        midpoint,
        label: edge.metadata.relationship_name || '',
      };
    });
  }, [visibleEdges, nodeIdToBox]);

  // Render a single class box
  const renderClassBox = (box: ClassBox) => {
    const { node, x, y, width, height } = box;
    const isSelected = node.id === selectedNodeId;
    
    const columns = node.metadata.columns || {};
    const columnEntries = Object.entries(columns);
    const displayedColumns = columnEntries.slice(0, 8);
    const hasMore = columnEntries.length > 8;
    const moreCount = columnEntries.length - 8;

    const headerHeight = 50;
    const attributeRowHeight = 20;

    return (
      <g
        key={node.id}
        onClick={() => onNodeSelect(node)}
        style={{ cursor: 'pointer' }}
        className="class-box"
      >
        {/* Main box */}
        <rect
          x={x}
          y={y}
          width={width}
          height={height}
          fill="white"
          stroke={isSelected ? '#FFD700' : '#333'}
          strokeWidth={isSelected ? 3 : 1}
          rx={4}
        />

        {/* Header section */}
        <rect
          x={x}
          y={y}
          width={width}
          height={headerHeight}
          fill="#F44336"
          fillOpacity={0.1}
          stroke="none"
        />

        {/* Stereotype */}
        <text
          x={x + width / 2}
          y={y + 15}
          textAnchor="middle"
          fontSize="10"
          fill="#666"
          fontStyle="italic"
        >
          «model»
        </text>

        {/* Class name */}
        <text
          x={x + width / 2}
          y={y + 35}
          textAnchor="middle"
          fontSize="14"
          fontWeight="bold"
          fill="#333"
        >
          {node.label}
        </text>

        {/* Divider after header */}
        <line
          x1={x}
          y1={y + headerHeight}
          x2={x + width}
          y2={y + headerHeight}
          stroke="#333"
          strokeWidth={1}
        />

        {/* Attributes section */}
        {displayedColumns.length > 0 ? (
          displayedColumns.map((col, index) => {
            const [colName, colInfo] = col;
            const attrY = y + headerHeight + (index + 1) * attributeRowHeight - 5;
            return (
              <text
                key={colName}
                x={x + 10}
                y={attrY}
                fontSize="11"
                fill="#333"
                fontFamily="monospace"
              >
                + {colName}: {colInfo.type}
              </text>
            );
          })
        ) : (
          <text
            x={x + 10}
            y={y + headerHeight + attributeRowHeight - 5}
            fontSize="11"
            fill="#999"
            fontStyle="italic"
          >
            (no columns)
          </text>
        )}

        {/* "... +N more" row */}
        {hasMore && (
          <text
            x={x + 10}
            y={y + headerHeight + (displayedColumns.length + 1) * attributeRowHeight - 5}
            fontSize="11"
            fill="#666"
            fontStyle="italic"
          >
            ... +{moreCount} more
          </text>
        )}

        {/* Divider before methods */}
        <line
          x1={x}
          y1={y + height - 30}
          x2={x + width}
          y2={y + height - 30}
          stroke="#333"
          strokeWidth={1}
        />

        {/* Hover effect */}
        <rect
          x={x}
          y={y}
          width={width}
          height={height}
          fill="transparent"
          stroke="transparent"
          strokeWidth={2}
          rx={4}
          className="hover-rect"
        />
      </g>
    );
  };

  // Export to PNG
  const exportToPNG = () => {
    if (!svgRef.current) return;

    const svgElement = svgRef.current;
    const svgData = new XMLSerializer().serializeToString(svgElement);
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const img = new Image();
    const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(svgBlob);

    img.onload = () => {
      canvas.width = svgDimensions.width;
      canvas.height = svgDimensions.height;
      ctx.fillStyle = 'white';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0);
      URL.revokeObjectURL(url);

      canvas.toBlob(blob => {
        if (!blob) return;
        const pngUrl = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.download = 'class-diagram.png';
        link.href = pngUrl;
        link.click();
        URL.revokeObjectURL(pngUrl);
      });
    };

    img.src = url;
  };

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {/* Toolbar */}
      <div
        style={{
          position: 'absolute',
          top: 10,
          left: 10,
          zIndex: 10,
          background: 'white',
          padding: '10px',
          borderRadius: '4px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
        }}
      >
        {/* Search */}
        <input
          type="text"
          placeholder="Search classes..."
          value={searchTerm}
          onChange={e => setSearchTerm(e.target.value)}
          style={{
            padding: '6px 10px',
            border: '1px solid #ddd',
            borderRadius: '4px',
            fontSize: '13px',
            width: '200px',
          }}
        />

        {/* Hide isolated toggle */}
        <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px' }}>
          <input
            type="checkbox"
            checked={hideIsolated}
            onChange={e => setHideIsolated(e.target.checked)}
          />
          Hide isolated models
        </label>

        {/* Zoom controls */}
        <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
          <button
            onClick={() => setZoom(z => Math.max(0.25, z - 0.25))}
            style={{
              padding: '4px 10px',
              border: '1px solid #ddd',
              borderRadius: '4px',
              background: 'white',
              cursor: 'pointer',
              fontSize: '14px',
            }}
          >
            −
          </button>
          <span style={{ fontSize: '12px', minWidth: '50px', textAlign: 'center' }}>
            {Math.round(zoom * 100)}%
          </span>
          <button
            onClick={() => setZoom(z => Math.min(2, z + 0.25))}
            style={{
              padding: '4px 10px',
              border: '1px solid #ddd',
              borderRadius: '4px',
              background: 'white',
              cursor: 'pointer',
              fontSize: '14px',
            }}
          >
            +
          </button>
        </div>

        {/* Export PNG */}
        <button
          onClick={exportToPNG}
          style={{
            padding: '6px 10px',
            border: '1px solid #ddd',
            borderRadius: '4px',
            background: '#4CAF50',
            color: 'white',
            cursor: 'pointer',
            fontSize: '13px',
            fontWeight: 500,
          }}
        >
          Export PNG
        </button>
      </div>

      {/* Scrollable canvas */}
      <div
        style={{
          width: '100%',
          height: '100%',
          overflow: 'auto',
          background: '#f9f9f9',
        }}
      >
        <svg
          ref={svgRef}
          width={svgDimensions.width}
          height={svgDimensions.height}
          style={{
            transform: `scale(${zoom})`,
            transformOrigin: 'top left',
          }}
        >
          {/* Arrow marker definition */}
          <defs>
            <marker
              id="arrowhead"
              markerWidth="10"
              markerHeight="10"
              refX="9"
              refY="3"
              orient="auto"
              markerUnits="strokeWidth"
            >
              <path d="M0,0 L0,6 L9,3 z" fill="#F44336" />
            </marker>
          </defs>

          {/* Render edges first (so they appear behind boxes) */}
          {edgePaths.map((path, index) => (
            <g key={index}>
              {/* Edge line */}
              <line
                x1={path.start.x}
                y1={path.start.y}
                x2={path.end.x}
                y2={path.end.y}
                stroke="#F44336"
                strokeWidth={2}
                markerEnd="url(#arrowhead)"
              />

              {/* Edge label */}
              {path.label && (
                <>
                  <rect
                    x={path.midpoint.x - 40}
                    y={path.midpoint.y - 10}
                    width={80}
                    height={20}
                    fill="white"
                    stroke="#F44336"
                    strokeWidth={1}
                    rx={3}
                  />
                  <text
                    x={path.midpoint.x}
                    y={path.midpoint.y + 4}
                    textAnchor="middle"
                    fontSize="10"
                    fill="#F44336"
                    fontWeight="500"
                  >
                    {path.label}
                  </text>
                </>
              )}
            </g>
          ))}

          {/* Render class boxes */}
          {classBoxes.map(renderClassBox)}
        </svg>
      </div>

      {/* Hover effect styles */}
      <style>{`
        .class-box:hover .hover-rect {
          stroke: #666;
          stroke-width: 2;
        }
      `}</style>
    </div>
  );
};

export default ClassDiagram;
