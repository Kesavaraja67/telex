/**
 * NodeRenderer — manages Three.js meshes for all file-site nodes.
 *
 * Visual states (never red/green):
 *  DORMANT   → dim white sphere, slow idle bob
 *  ACTIVE    → bright white, amber pulse begins on wire
 *  PATCHING  → medium white, amber wire glow
 *  FAILED    → desaturated flicker + wire thinning (no red)
 *  VERIFIED  → brief teal shift, then steady white
 *  RESOLVED  → calm outer ring, resting glow
 *
 * Geometry and material are pooled by state — no per-frame allocations.
 */

import * as THREE from "three";

export const NODE_STATUS = {
  DORMANT:  0,
  ACTIVE:   1,
  PATCHING: 2,
  FAILED:   3,
  VERIFIED: 4,
  RESOLVED: 5,
} as const;
export type NodeStatusValue = (typeof NODE_STATUS)[keyof typeof NODE_STATUS];

interface NodeEntry {
  mesh: THREE.Mesh;
  glow: THREE.Mesh;
  status: NodeStatusValue;
  radius: number;
  flickerPhase: number;
}

// Shared material pool — one material per status variant
const GEO_CACHE = new Map<number, THREE.SphereGeometry>();
const getGeo = (r: number): THREE.SphereGeometry => {
  const key = Math.round(r * 100);
  if (!GEO_CACHE.has(key)) GEO_CACHE.set(key, new THREE.SphereGeometry(r, 24, 16));
  return GEO_CACHE.get(key)!;
};

const MATERIAL_POOL: Record<NodeStatusValue, THREE.MeshPhysicalMaterial> = {
  [NODE_STATUS.DORMANT]: new THREE.MeshPhysicalMaterial({
    color: 0x888888, emissive: 0x444444, emissiveIntensity: 0.2,
    roughness: 0.4, metalness: 0.5,
  }),
  [NODE_STATUS.ACTIVE]: new THREE.MeshPhysicalMaterial({
    color: 0xffffff, emissive: 0xffffff, emissiveIntensity: 0.55,
    roughness: 0.18, metalness: 0.6, clearcoat: 0.6,
  }),
  [NODE_STATUS.PATCHING]: new THREE.MeshPhysicalMaterial({
    color: 0xffffff, emissive: 0xe5a93c, emissiveIntensity: 0.35,
    roughness: 0.22, metalness: 0.55,
  }),
  [NODE_STATUS.FAILED]: new THREE.MeshPhysicalMaterial({
    color: 0x555555, emissive: 0x222222, emissiveIntensity: 0.1,
    roughness: 0.65, metalness: 0.3,
  }),
  [NODE_STATUS.VERIFIED]: new THREE.MeshPhysicalMaterial({
    color: 0x5eead4, emissive: 0x5eead4, emissiveIntensity: 0.5,
    roughness: 0.15, metalness: 0.6, clearcoat: 0.9,
  }),
  [NODE_STATUS.RESOLVED]: new THREE.MeshPhysicalMaterial({
    color: 0xcccccc, emissive: 0x888888, emissiveIntensity: 0.12,
    roughness: 0.35, metalness: 0.5,
  }),
};

const GLOW_POOL: Record<NodeStatusValue, THREE.MeshBasicMaterial> = {
  [NODE_STATUS.DORMANT]:  new THREE.MeshBasicMaterial({ color: 0x333333, transparent: true, opacity: 0.04, blending: THREE.AdditiveBlending, side: THREE.BackSide, depthWrite: false }),
  [NODE_STATUS.ACTIVE]:   new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.10, blending: THREE.AdditiveBlending, side: THREE.BackSide, depthWrite: false }),
  [NODE_STATUS.PATCHING]: new THREE.MeshBasicMaterial({ color: 0xe5a93c, transparent: true, opacity: 0.12, blending: THREE.AdditiveBlending, side: THREE.BackSide, depthWrite: false }),
  [NODE_STATUS.FAILED]:   new THREE.MeshBasicMaterial({ color: 0x222222, transparent: true, opacity: 0.03, blending: THREE.AdditiveBlending, side: THREE.BackSide, depthWrite: false }),
  [NODE_STATUS.VERIFIED]: new THREE.MeshBasicMaterial({ color: 0x5eead4, transparent: true, opacity: 0.22, blending: THREE.AdditiveBlending, side: THREE.BackSide, depthWrite: false }),
  [NODE_STATUS.RESOLVED]: new THREE.MeshBasicMaterial({ color: 0x888888, transparent: true, opacity: 0.06, blending: THREE.AdditiveBlending, side: THREE.BackSide, depthWrite: false }),
};

export class NodeRenderer {
  private entries = new Map<string, NodeEntry>();
  private clock = 0;

  constructor(private scene: THREE.Scene) {
    // Start a per-frame update for flicker — called from OrganismScene's tick
    // via the scene's traverse or setPosition calls
  }

  add(id: string, radius: number, status: NodeStatusValue = NODE_STATUS.DORMANT) {
    const geo = getGeo(radius);
    const glowGeo = getGeo(radius * 1.5);

    const mesh = new THREE.Mesh(geo, MATERIAL_POOL[status].clone());
    const glow = new THREE.Mesh(glowGeo, GLOW_POOL[status].clone());
    glow.renderOrder = -1;

    this.scene.add(mesh);
    this.scene.add(glow);

    this.entries.set(id, { mesh, glow, status, radius, flickerPhase: Math.random() * Math.PI * 2 });
  }

  setStatus(id: string, status: NodeStatusValue) {
    const entry = this.entries.get(id);
    if (!entry || entry.status === status) return;
    entry.status = status;

    // Clone from pool so we can animate emissiveIntensity per-node without
    // affecting other nodes sharing the same status
    const newMat = MATERIAL_POOL[status].clone();
    const newGlow = GLOW_POOL[status].clone();
    (entry.mesh.material as THREE.Material).dispose();
    (entry.glow.material as THREE.Material).dispose();
    entry.mesh.material = newMat;
    entry.glow.material = newGlow;

    // Brief scale pop for state transitions
    entry.mesh.scale.setScalar(1.3);
    setTimeout(() => {
      if (entry.mesh) entry.mesh.scale.setScalar(1.0);
    }, 250);
  }

  setPosition(id: string, x: number, y: number, z: number) {
    const entry = this.entries.get(id);
    if (!entry) return;
    entry.mesh.position.set(x, y, z);
    entry.glow.position.set(x, y, z);

    // Per-node animation effects keyed off scene clock (accessed via id's flickerPhase)
    this.clock += 0.00016; // tiny increment so all nodes drift independently
    this._animateEntry(entry, this.clock);
  }

  private _animateEntry(entry: NodeEntry, t: number) {
    const mat = entry.mesh.material as THREE.MeshPhysicalMaterial;
    const glowMat = entry.glow.material as THREE.MeshBasicMaterial;
    const phase = entry.flickerPhase;

    switch (entry.status) {
      case NODE_STATUS.DORMANT:
        // Slow idle breath
        mat.emissiveIntensity = 0.15 + Math.sin(t * 0.8 + phase) * 0.05;
        break;
      case NODE_STATUS.ACTIVE:
        mat.emissiveIntensity = 0.45 + Math.sin(t * 3.5 + phase) * 0.12;
        break;
      case NODE_STATUS.PATCHING:
        mat.emissiveIntensity = 0.3 + Math.sin(t * 4.0 + phase) * 0.1;
        break;
      case NODE_STATUS.FAILED: {
        // Irregular desaturating flicker — NOT red, just going dark and grey
        const flicker = Math.random() > 0.94 ? 0.25 : 0.0;
        mat.emissiveIntensity = 0.06 + flicker;
        glowMat.opacity = 0.02 + flicker * 0.04;
        break;
      }
      case NODE_STATUS.VERIFIED:
        // Brief teal, then calm white — handled by status transitions
        mat.emissiveIntensity = 0.45 + Math.sin(t * 2.0 + phase) * 0.08;
        break;
      case NODE_STATUS.RESOLVED:
        mat.emissiveIntensity = 0.10 + Math.sin(t * 0.6 + phase) * 0.03;
        break;
    }
  }

  dispose() {
    for (const [, entry] of this.entries) {
      this.scene.remove(entry.mesh);
      this.scene.remove(entry.glow);
      (entry.mesh.material as THREE.Material).dispose();
      (entry.glow.material as THREE.Material).dispose();
    }
    this.entries.clear();
    for (const [, geo] of GEO_CACHE) geo.dispose();
    GEO_CACHE.clear();
  }
}
