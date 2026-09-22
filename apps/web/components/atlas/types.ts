export interface AtlasNode {
  id: string;
  name: string;
  dir: string;
  depth: number;
  ext: string;
  language: string | null;
  is_binary: boolean;
  size_bytes: number;
  unresolved_import_count: number;
  unresolved_specifiers: string[];
}

export interface AtlasEdge {
  source: string;
  target: string;
  kind: "import";
}

export interface AtlasFolder {
  id: string;
  name: string;
  parent: string | null;
  depth: number;
}

export interface AtlasGraphPayload {
  status: "ready";
  commit_sha: string;
  node_count: number;
  edge_count: number;
  truncated: boolean;
  graph: {
    nodes: AtlasNode[];
    edges: AtlasEdge[];
    folders: AtlasFolder[];
    truncated: boolean;
  };
}

export interface AtlasSelection {
  nodeId: string;
  brokenBy: string[]; // detected_change_ids currently implicating this file, [] if none
  node?: AtlasNode;
}

export interface ActiveIncident {
  detected_change_id: string;
  package: string;
  symbol_old: string;
  symbol_new: string;
  change_type: string;
}
