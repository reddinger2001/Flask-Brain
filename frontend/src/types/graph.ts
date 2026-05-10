export type NodeType = 'blueprint' | 'route' | 'action' | 'service' | 'model' | 'task' | 'property';

export type EdgeType = 'calls' | 'registers_blueprint' | 'has_relationship' | 'uses_model' | 'dispatches_task' | 'defines_property' | 'reads_property' | 'writes_property';

export type ComplexityTier = 'low' | 'moderate' | 'high' | 'critical';

export interface DBOperation {
  type: 'READ' | 'WRITE';
  pattern: string;
}

export interface NodeMetadata {
  // Blueprint metadata
  url_prefix?: string;
  
  // Route metadata
  methods?: string[];
  view_function?: string;
  blueprint?: string;
  
  // Action/Service metadata
  complexity?: number;
  line_count?: number;
  complexity_tier?: ComplexityTier;
  db_operations?: DBOperation[];
  db_op_count?: number;
  service_methods?: string[];
  is_fat?: boolean;
  
  // Model metadata
  columns?: Record<string, { type: string }>;
  relationships?: string[];
  
  // Task metadata
  queue?: string;
  
  // Relationship metadata
  relationship_name?: string;

  // Git churn / risk metadata (from GitChurnAnalyzer)
  churn_count?: number;
  risk_score?: number;
}

export interface Node {
  id: string;
  type: NodeType;
  label: string;
  file_path: string;
  line_number: number;
  metadata: NodeMetadata;
}

export interface EdgeMetadata {
  relationship_name?: string;
}

export interface Edge {
  source: string;
  target: string;
  type: EdgeType;
  metadata: EdgeMetadata;
}

export interface Graph {
  nodes: Node[];
  edges: Edge[];
}

export interface Manifest {
  project_name: string;
  scan_timestamp: string;
  node_count: number;
  edge_count: number;
  node_types: Record<string, number>;
}

export interface SourceResponse {
  content: string;
  path: string;
  line: number;
}
