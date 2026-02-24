export type NodeType = "core" | "normal" | "counterexample" | "skeleton" | "question";
export type EdgeType = "normal" | "bridge" | "counter" | "redirect";

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
  mastery: number;
  importance: number;
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
  question: string;
  source_section_key?: string | null;
  strength: number;
  edge_type: EdgeType;
  created_at: string;
}

export interface GraphData {
  nodes: NodeItem[];
  edges: EdgeItem[];
}
