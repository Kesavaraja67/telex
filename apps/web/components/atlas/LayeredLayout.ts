import * as d3Force from "d3-force-3d";
import type { AtlasFolder, AtlasGraphPayload, AtlasNode } from "./types";

export const LAYER_SPACING = 3.2; // vertical distance between hierarchy layers
export const CARD_WIDTH = 1.6;
export const CARD_HEIGHT = 1.0;

export interface LayoutFolderAnchor {
  id: string;
  name: string;
  depth: number;
  parent: string | null;
  x: number;
  y: number;
  z: number;
}

export interface LayoutNodePosition {
  id: string;
  name: string;
  dir: string;
  depth: number;
  x: number;
  y: number;
  z: number;
  folderId: string;
  node: AtlasNode;
}

export interface LayeredLayoutResult {
  folderAnchors: Map<string, LayoutFolderAnchor>;
  nodePositions: Map<string, LayoutNodePosition>;
}

interface SimNode {
  id: string;
  x: number;
  y: number;
  z: number;
  targetX: number;
  targetZ: number;
  vx?: number;
  vy?: number;
  vz?: number;
}

export class LayeredLayout {
  /**
   * Computes deterministic folder anchors and constrained 2D collision-settled
   * file card positions for each layer.
   */
  static compute(graphPayload: AtlasGraphPayload["graph"]): LayeredLayoutResult {
    const { nodes, folders } = graphPayload;

    // 1. Organize folders by parent and depth
    const foldersById = new Map<string, AtlasFolder>();
    folders.forEach((f) => foldersById.set(f.id, f));

    // Ensure root folder exists
    if (!foldersById.has("")) {
      foldersById.set("", { id: "", name: "/", parent: null, depth: 0 });
    }

    const folderChildren = new Map<string, string[]>();
    foldersById.forEach((f) => {
      const p = f.parent ?? "";
      if (f.id !== "") {
        if (!folderChildren.has(p)) folderChildren.set(p, []);
        folderChildren.get(p)!.push(f.id);
      }
    });

    // 2. Deterministic polar placement of folder anchors
    const folderAnchors = new Map<string, LayoutFolderAnchor>();
    folderAnchors.set("", {
      id: "",
      name: "/",
      depth: 0,
      parent: null,
      x: 0,
      y: 0,
      z: 0,
    });

    // Traverse breadth-first from root
    const queue: string[] = [""];
    while (queue.length > 0) {
      const parentId = queue.shift()!;
      const parentAnchor = folderAnchors.get(parentId)!;
      const children = folderChildren.get(parentId) || [];
      const siblingCount = children.length;
      if (siblingCount === 0) continue;

      const radius = 2.8 + 0.45 * siblingCount;
      const angleStep = (2 * Math.PI) / siblingCount;

      children.sort().forEach((childId, idx) => {
        const childFolder = foldersById.get(childId)!;
        const angle = idx * angleStep;
        const x = parentAnchor.x + radius * Math.cos(angle);
        const z = parentAnchor.z + radius * Math.sin(angle);
        const y = -childFolder.depth * LAYER_SPACING;

        folderAnchors.set(childId, {
          id: childId,
          name: childFolder.name,
          depth: childFolder.depth,
          parent: parentId,
          x,
          y,
          z,
        });

        queue.push(childId);
      });
    }

    // 3. Assign nodes to folders and seed initial ring/grid around folder anchor
    const filesByFolder = new Map<string, AtlasNode[]>();
    nodes.forEach((node) => {
      const folderKey = node.dir.replace(/\\/g, "/");
      const matchedFolder = folderAnchors.has(folderKey) ? folderKey : "";
      if (!filesByFolder.has(matchedFolder)) filesByFolder.set(matchedFolder, []);
      filesByFolder.get(matchedFolder)!.push(node);
    });

    const simNodes: SimNode[] = [];
    const nodeMetaMap = new Map<string, { folderId: string; node: AtlasNode; fixedY: number }>();

    filesByFolder.forEach((folderFiles, folderId) => {
      const anchor = folderAnchors.get(folderId) || folderAnchors.get("")!;
      const fileCount = folderFiles.length;
      const ringRadius = Math.max(1.4, Math.ceil(Math.sqrt(fileCount)) * 0.95);
      const angleStep = (2 * Math.PI) / Math.max(1, fileCount);
      const fixedY = -anchor.depth * LAYER_SPACING;

      folderFiles.forEach((fNode, idx) => {
        const angle = idx * angleStep;
        // Distribute in concentric rings if many files
        const tier = Math.floor(idx / 12);
        const currentR = ringRadius + tier * 1.5;
        const seedX = anchor.x + currentR * Math.cos(angle);
        const seedZ = anchor.z + currentR * Math.sin(angle);

        simNodes.push({
          id: fNode.id,
          x: seedX,
          y: fixedY,
          z: seedZ,
          targetX: anchor.x,
          targetZ: anchor.z,
        });

        nodeMetaMap.set(fNode.id, {
          folderId,
          node: fNode,
          fixedY,
        });
      });
    });

    // 4. Constrained 2D force simulation (X/Z only, Y remains untouched)
    // Run bounded ticks synchronously
    if (simNodes.length > 0) {
      const simulation = d3Force
        .forceSimulation(simNodes, 3)
        .force(
          "collide",
          d3Force.forceCollide(1.05).iterations(2) // Card footprint clearance
        )
        .force("x", d3Force.forceX((d: any) => d.targetX).strength(0.08))
        .force("z", d3Force.forceZ((d: any) => d.targetZ).strength(0.08))
        .stop();

      const TICKS = Math.min(180, Math.max(60, Math.floor(simNodes.length / 5)));
      for (let i = 0; i < TICKS; i++) {
        simulation.tick();
      }
    }

    // 5. Build final position map
    const nodePositions = new Map<string, LayoutNodePosition>();
    simNodes.forEach((sn) => {
      const meta = nodeMetaMap.get(sn.id)!;
      nodePositions.set(sn.id, {
        id: sn.id,
        name: meta.node.name,
        dir: meta.node.dir,
        depth: meta.node.depth,
        x: sn.x,
        y: meta.fixedY, // Strictly preserve folder layer depth Y
        z: sn.z,
        folderId: meta.folderId,
        node: meta.node,
      });
    });

    return {
      folderAnchors,
      nodePositions,
    };
  }
}
