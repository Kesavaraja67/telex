/**
 * WireRenderer — dynamic CatmullRomCurve3 wires connecting root → each node.
 *
 * Each wire is:
 *  1. A thin TubeGeometry (main wire)
 *  2. A wider, additive-blended low-opacity duplicate behind it (glow)
 *  3. Up to N traveling pulse sprites per wire (amber out, teal in)
 *
 * No EffectComposer bloom — faked via additive geometry exactly as in the plan.
 * TubeGeometry is recreated each frame from current node positions (the curve
 * changes as the simulation drifts). Material is reused — only geometry is rebuilt.
 */

import * as THREE from "three";

const MAX_PULSES_DESKTOP = 40;
const MAX_PULSES_MOBILE = 12;

interface Pulse {
  wireId: string;
  direction: "out" | "in"; // out = root→node (amber), in = node→root (teal)
  t: number;               // 0..1 along curve
  speed: number;
  startTime: number;
  mesh: THREE.Mesh;
}

interface WireEntry {
  nodePos: THREE.Vector3;
  mainMesh: THREE.Mesh | null;
  glowMesh: THREE.Mesh | null;
  mainMat: THREE.MeshBasicMaterial;
  glowMat: THREE.MeshBasicMaterial;
}

const ROOT = new THREE.Vector3(0, 0, 0);

const PULSE_GEO = new THREE.SphereGeometry(0.10, 8, 6);

const makePulseMat = (isOut: boolean) =>
  new THREE.MeshBasicMaterial({
    color: isOut ? 0xe5a93c : 0x5eead4,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    transparent: true,
    opacity: 0.9,
  });

export class WireRenderer {
  private wires = new Map<string, WireEntry>();
  private pulses: Pulse[] = [];
  private isMobile = typeof window !== "undefined"
    ? window.matchMedia("(max-width: 768px)").matches
    : false;

  constructor(private scene: THREE.Scene) {}

  add(id: string) {
    if (this.wires.has(id)) return;
    this.wires.set(id, {
      nodePos: new THREE.Vector3(5, 0, 0),
      mainMesh: null,
      glowMesh: null,
      mainMat: new THREE.MeshBasicMaterial({
        color: 0x555555,
        transparent: true,
        opacity: 0.6,
      }),
      glowMat: new THREE.MeshBasicMaterial({
        color: 0x888888,
        transparent: true,
        opacity: 0.08,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    });
  }

  setNodePosition(id: string, x: number, y: number, z: number) {
    const w = this.wires.get(id);
    if (!w) return;
    w.nodePos.set(x, y, z);
    this._rebuildWire(id, w);
  }

  addPulse(wireId: string, direction: "out" | "in", clockTime: number) {
    const maxP = this.isMobile ? MAX_PULSES_MOBILE : MAX_PULSES_DESKTOP;
    if (this.pulses.length >= maxP) {
      // Remove oldest
      const oldest = this.pulses.shift()!;
      this.scene.remove(oldest.mesh);
      oldest.mesh.material.dispose();
    }

    const pulseMesh = new THREE.Mesh(PULSE_GEO, makePulseMat(direction === "out"));
    this.scene.add(pulseMesh);
    this.pulses.push({
      wireId,
      direction,
      t: direction === "out" ? 0 : 1,
      speed: 0.4 + Math.random() * 0.2,
      startTime: clockTime,
      mesh: pulseMesh,
    });
  }

  tick(clockTime: number, reduced: boolean) {
    const dead: number[] = [];

    for (let i = 0; i < this.pulses.length; i++) {
      const p = this.pulses[i];
      const w = this.wires.get(p.wireId);
      if (!w) { dead.push(i); continue; }

      if (!reduced) {
        p.t += p.direction === "out" ? p.speed * 0.016 : -p.speed * 0.016;
      }

      if (p.t < 0 || p.t > 1) {
        dead.push(i);
        this.scene.remove(p.mesh);
        (p.mesh.material as THREE.Material).dispose();
        continue;
      }

      // Place pulse along the curve
      const pos = this._curvePointAt(w.nodePos, p.t);
      p.mesh.position.copy(pos);

      // Fade near endpoints
      const fade = Math.min(p.t, 1 - p.t) * 6;
      (p.mesh.material as THREE.MeshBasicMaterial).opacity = Math.min(0.9, fade);
    }

    for (let i = dead.length - 1; i >= 0; i--) {
      this.pulses.splice(dead[i], 1);
    }
  }

  dispose() {
    for (const [, w] of this.wires) {
      if (w.mainMesh) { this.scene.remove(w.mainMesh); w.mainMesh.geometry.dispose(); w.mainMat.dispose(); }
      if (w.glowMesh) { this.scene.remove(w.glowMesh); w.glowMesh.geometry.dispose(); w.glowMat.dispose(); }
    }
    for (const p of this.pulses) {
      this.scene.remove(p.mesh);
      (p.mesh.material as THREE.Material).dispose();
    }
    PULSE_GEO.dispose();
    this.wires.clear();
    this.pulses = [];
  }

  private _rebuildWire(id: string, w: WireEntry) {
    const mid = new THREE.Vector3(
      w.nodePos.x * 0.5 + (Math.sin(w.nodePos.x) * 1.2),
      w.nodePos.y * 0.5 + 1.5,
      w.nodePos.z * 0.5 + (Math.cos(w.nodePos.z) * 1.2)
    );
    const curve = new THREE.CatmullRomCurve3([ROOT, mid, w.nodePos]);
    const mainGeo = new THREE.TubeGeometry(curve, 20, 0.025, 6, false);
    const glowGeo = new THREE.TubeGeometry(curve, 12, 0.055, 6, false);

    if (w.mainMesh) {
      this.scene.remove(w.mainMesh);
      w.mainMesh.geometry.dispose();
    }
    if (w.glowMesh) {
      this.scene.remove(w.glowMesh);
      w.glowMesh.geometry.dispose();
    }

    w.mainMesh = new THREE.Mesh(mainGeo, w.mainMat);
    w.glowMesh = new THREE.Mesh(glowGeo, w.glowMat);
    w.glowMesh.renderOrder = -1;

    this.scene.add(w.mainMesh);
    this.scene.add(w.glowMesh);
  }

  private _curvePointAt(nodePos: THREE.Vector3, t: number): THREE.Vector3 {
    const mid = new THREE.Vector3(
      nodePos.x * 0.5 + Math.sin(nodePos.x) * 1.2,
      nodePos.y * 0.5 + 1.5,
      nodePos.z * 0.5 + Math.cos(nodePos.z) * 1.2
    );
    const curve = new THREE.CatmullRomCurve3([ROOT, mid, nodePos]);
    return curve.getPoint(t);
  }
}
