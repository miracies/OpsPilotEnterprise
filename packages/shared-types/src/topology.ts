export interface TopologyNode {
  id: string;
  name: string;
  type: string;
  status?: string;
  metadata?: Record<string, unknown>;
}

export interface TopologyEdge {
  id: string;
  source: string;
  target: string;
  relation: string;
  metadata?: Record<string, unknown>;
}

export interface TopologyGraph {
  graph_id: string;
  connection_id: string;
  generated_at: string;
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  metadata?: Record<string, unknown>;
}
