/**
 * OrganismSimulation — 3D spring/repulsion layout using d3-force-3d.
 *
 * Root is fixed at (0,0,0). File nodes repel each other and are
 * spring-linked to the root. Continuous low-alpha tick with velocity
 * damping creates the organic living drift described in the plan.
 */

// eslint-disable-next-line @typescript-eslint/no-require-imports
const d3Force3d = require("d3-force-3d");

interface SimNode {
  id: string;
  x: number;
  y: number;
  z: number;
  vx?: number;
  vy?: number;
  vz?: number;
  fx?: number | null;
  fy?: number | null;
  fz?: number | null;
  lineCount: number;
}

interface SimLink {
  source: string;
  target: string;
  strength: number;
}

export class OrganismSimulation {
  private nodes: SimNode[] = [];
  private links: SimLink[] = [];
  private sim: ReturnType<typeof d3Force3d.forceSimulation>;
  private nodeMap = new Map<string, SimNode>();

  private readonly ROOT_ID = "__root__";

  constructor() {
    const rootNode: SimNode = {
      id: this.ROOT_ID,
      x: 0,
      y: 0,
      z: 0,
      fx: 0,
      fy: 0,
      fz: 0,
      lineCount: 0,
    };
    this.nodes.push(rootNode);
    this.nodeMap.set(this.ROOT_ID, rootNode);
    this._buildSim();
  }

  addNode(id: string, lineCount: number): SimNode {
    if (this.nodeMap.has(id)) return this.nodeMap.get(id)!;

    const angle = Math.random() * Math.PI * 2;
    const elevation = (Math.random() - 0.5) * Math.PI;
    const r = 4 + Math.random() * 2;
    const node: SimNode = {
      id,
      lineCount,
      x: r * Math.cos(angle) * Math.cos(elevation),
      y: r * Math.sin(elevation),
      z: r * Math.sin(angle) * Math.cos(elevation),
    };
    this.nodes.push(node);
    this.nodeMap.set(id, node);

    this.links.push({ source: this.ROOT_ID, target: id, strength: 0.04 });

    this._buildSim();
    return node;
  }

  getPosition(id: string): { x: number; y: number; z: number } | null {
    const n = this.nodeMap.get(id);
    return n ? { x: n.x, y: n.y, z: n.z } : null;
  }

  tick() {
    // Called each animation frame — restores a small alpha for organic drift
    if (this.sim.alpha() < 0.01) {
      this.sim.alpha(0.02);
    }
    this.sim.tick(1);
  }

  private _buildSim() {
    if (this.sim) this.sim.stop();

    const linkForce = d3Force3d
      .forceLink(this.links)
      .id((d: SimNode) => d.id)
      .distance((l: SimLink) => {
        // Longer links for weaker connections — but capped
        return 5 + (1 - (l.strength || 0.04) / 0.1) * 2;
      })
      .strength((l: SimLink) => l.strength);

    this.sim = d3Force3d
      .forceSimulation(this.nodes, 3) // numDimensions=3
      .force("link", linkForce)
      .force(
        "charge",
        d3Force3d.forceManyBody().strength(-18).distanceMax(20)
      )
      .force("center", d3Force3d.forceCenter(0, 0, 0).strength(0.005))
      .velocityDecay(0.55)
      .alpha(0.3)
      .alphaMin(0.001)
      .alphaDecay(0.005);
  }
}
