export type NodeType = "core" | "normal" | "counterexample" | "skeleton" | "question" | "answer" | "knowledge";
export type EdgeType = "direct";

export interface Session {
  id: string;
  topic: string;
  created_at: string;
}

export interface SelectedSection {
  node_id: string;
  title: string;
  body: string;
  key?: string;
}

export interface NodeItem {
  id: string;
  session_id: string;
  title: string;
  content: string;
  x: number;
  y: number;
  width: number;
  node_type: NodeType;
  created_at: string;
}

export interface EdgeItem {
  id: string;
  session_id: string;
  source_node_id: string;
  target_node_id: string;
  source_section_key?: string | null;
  edge_type: EdgeType;
  created_at: string;
}

export interface GraphData {
  nodes: NodeItem[];
  edges: EdgeItem[];
}
