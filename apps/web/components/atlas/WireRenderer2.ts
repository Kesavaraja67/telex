import * as THREE from "three";
import type { AtlasEdge } from "./types";
import type { LayoutFolderAnchor, LayoutNodePosition } from "./LayeredLayout";

interface ImportWire {
  id: string;
  sourceId: string;
  targetId: string;
  curve: THREE.QuadraticBezierCurve3;
  lineMesh: THREE.Line;
  pulseMesh: THREE.Mesh;
  pulseProgress: number; // 0 to 1
  pulseSpeed: number;
  isSevered: boolean;
}

const PULSE_GEO = new THREE.SphereGeometry(0.06, 8, 8);
const NORMAL_PULSE_MAT = new THREE.MeshBasicMaterial({
  color: 0x5eead4,
});
const BROKEN_PULSE_MAT = new THREE.MeshBasicMaterial({
  color: 0xe11d48,
});

export class WireRenderer2 {
  private scene: THREE.Scene;
  private structuralLines: THREE.LineSegments | null = null;
  private importWires: ImportWire[] = [];
  private brokenNodeIds = new Set<string>();
  private isMobile: boolean;

  constructor(scene: THREE.Scene, isMobile: boolean = false) {
    this.scene = scene;
    this.isMobile = isMobile;
  }

  setBreakage(brokenNodeIds: Set<string>) {
    this.brokenNodeIds = brokenNodeIds;
    this.importWires.forEach((w) => {
      const isBroken = this.brokenNodeIds.has(w.sourceId) || this.brokenNodeIds.has(w.targetId);
      if (w.isSevered !== isBroken) {
        w.isSevered = isBroken;
        const mat = w.lineMesh.material as THREE.LineBasicMaterial | THREE.LineDashedMaterial;
        if (isBroken) {
          mat.color.setHex(0xe11d48);
          mat.transparent = true;
          mat.opacity = 0.75;
          w.pulseMesh.material = BROKEN_PULSE_MAT;
        } else {
          mat.color.setHex(0x5eead4);
          mat.transparent = true;
          mat.opacity = 0.35;
          w.pulseMesh.material = NORMAL_PULSE_MAT;
        }
      }
    });
  }

  build(
    folderAnchors: Map<string, LayoutFolderAnchor>,
    nodePositions: Map<string, LayoutNodePosition>,
    edges: AtlasEdge[]
  ) {
    this.clear();

    // 1. Build structural lines (parent folder -> child folder, folder -> child files)
    const structPoints: THREE.Vector3[] = [];

    // Folder hierarchy lines
    folderAnchors.forEach((folder) => {
      if (folder.parent !== null) {
        const parent = folderAnchors.get(folder.parent);
        if (parent) {
          structPoints.push(new THREE.Vector3(parent.x, parent.y, parent.z));
          structPoints.push(new THREE.Vector3(folder.x, folder.y, folder.z));
        }
      }
    });

    // Folder anchor -> contained file cards
    nodePositions.forEach((node) => {
      const folder = folderAnchors.get(node.folderId);
      if (folder) {
        structPoints.push(new THREE.Vector3(folder.x, folder.y, folder.z));
        structPoints.push(new THREE.Vector3(node.x, node.y, node.z));
      }
    });

    if (structPoints.length > 0) {
      const structGeo = new THREE.BufferGeometry().setFromPoints(structPoints);
      const structMat = new THREE.LineBasicMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: 0.12,
      });
      this.structuralLines = new THREE.LineSegments(structGeo, structMat);
      this.scene.add(this.structuralLines);
    }

    // 2. Build import wires
    edges.forEach((edge, idx) => {
      const source = nodePositions.get(edge.source);
      const target = nodePositions.get(edge.target);
      if (!source || !target) return;

      const p1 = new THREE.Vector3(source.x, source.y, source.z);
      const p2 = new THREE.Vector3(target.x, target.y, target.z);

      // Arc calculation: pull midpoint upward in local space
      const dist = p1.distanceTo(p2);
      const mid = new THREE.Vector3().addVectors(p1, p2).multiplyScalar(0.5);
      const arcHeight = Math.min(2.5, Math.max(0.4, dist * 0.18));
      mid.y += arcHeight;

      const curve = new THREE.QuadraticBezierCurve3(p1, mid, p2);
      const points = curve.getPoints(24);
      const geo = new THREE.BufferGeometry().setFromPoints(points);

      const isBroken = this.brokenNodeIds.has(edge.source) || this.brokenNodeIds.has(edge.target);
      const lineMat = new THREE.LineBasicMaterial({
        color: isBroken ? 0xe11d48 : 0x5eead4,
        transparent: true,
        opacity: isBroken ? 0.75 : 0.35,
      });

      const lineMesh = new THREE.Line(geo, lineMat);
      this.scene.add(lineMesh);

      // Traveling pulse
      const pulseMesh = new THREE.Mesh(PULSE_GEO, isBroken ? BROKEN_PULSE_MAT : NORMAL_PULSE_MAT);
      pulseMesh.position.copy(p1);
      this.scene.add(pulseMesh);

      this.importWires.push({
        id: `${edge.source}->${edge.target}:${idx}`,
        sourceId: edge.source,
        targetId: edge.target,
        curve,
        lineMesh,
        pulseMesh,
        pulseProgress: Math.random(), // Stagger pulse starts
        pulseSpeed: 0.25 + Math.random() * 0.25,
        isSevered: isBroken,
      });
    });
  }

  updateNodePosition(nodeId: string, x: number, y: number, z: number) {
    this.importWires.forEach((wire) => {
      if (wire.sourceId === nodeId || wire.targetId === nodeId) {
        const p1 = wire.sourceId === nodeId ? new THREE.Vector3(x, y, z) : wire.curve.v0;
        const p2 = wire.targetId === nodeId ? new THREE.Vector3(x, y, z) : wire.curve.v2;

        const dist = p1.distanceTo(p2);
        const mid = new THREE.Vector3().addVectors(p1, p2).multiplyScalar(0.5);
        mid.y += Math.min(2.5, Math.max(0.4, dist * 0.18));

        wire.curve.v0.copy(p1);
        wire.curve.v1.copy(mid);
        wire.curve.v2.copy(p2);

        const pts = wire.curve.getPoints(24);
        wire.lineMesh.geometry.setFromPoints(pts);
      }
    });
  }

  update(delta: number) {
    const maxActivePulses = this.isMobile ? 25 : 120;
    const activeCount = Math.min(this.importWires.length, maxActivePulses);

    for (let i = 0; i < this.importWires.length; i++) {
      const wire = this.importWires[i];
      if (i < activeCount) {
        wire.pulseProgress = (wire.pulseProgress + delta * wire.pulseSpeed) % 1;
        const pt = wire.curve.getPoint(wire.pulseProgress);
        wire.pulseMesh.position.copy(pt);
        wire.pulseMesh.visible = true;
      } else {
        wire.pulseMesh.visible = false;
      }
    }
  }

  clear() {
    if (this.structuralLines) {
      this.scene.remove(this.structuralLines);
      this.structuralLines.geometry.dispose();
      (this.structuralLines.material as THREE.Material).dispose();
      this.structuralLines = null;
    }

    this.importWires.forEach((w) => {
      this.scene.remove(w.lineMesh);
      w.lineMesh.geometry.dispose();
      (w.lineMesh.material as THREE.Material).dispose();

      this.scene.remove(w.pulseMesh);
    });
    this.importWires = [];
  }

  dispose() {
    this.clear();
  }
}
