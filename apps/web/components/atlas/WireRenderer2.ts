import * as THREE from "three";
import type { AtlasEdge } from "./types";
import type { LayoutFolderAnchor, LayoutNodePosition } from "./LayeredLayout";

interface CometPulse {
  group: THREE.Group;
  spheres: THREE.Mesh[];
  materials: THREE.MeshBasicMaterial[];
}

interface ImportWire {
  id: string;
  sourceId: string;
  targetId: string;
  curve: THREE.QuadraticBezierCurve3;
  tubeMesh: THREE.Mesh;
  tubeGeo: THREE.TubeGeometry;
  tubeMat: THREE.MeshPhysicalMaterial;
  pulse: CometPulse;
  pulseProgress: number; // >= 0: in-flight along curve (0 to 1); < 0: idle cooldown
  pulseSpeed: number; // travel speed (takes ~1.6s - 2.4s to cross)
  isSevered: boolean;
  baseRadius: number;
}

interface SparkParticle {
  mesh: THREE.Mesh;
  vel: THREE.Vector3;
  life: number;
  maxLife: number;
}

// Proportional photon sphere geometries that snugly envelop the rounded rubber cable
const LEAD_PULSE_GEO = new THREE.SphereGeometry(0.046, 12, 12);
const TRAIL_GEOS = [
  new THREE.SphereGeometry(0.038, 10, 10),
  new THREE.SphereGeometry(0.028, 8, 8),
  new THREE.SphereGeometry(0.018, 8, 8),
];

const SPARK_GEO = new THREE.SphereGeometry(0.032, 6, 6);
const SPARK_MAT = new THREE.MeshBasicMaterial({
  color: 0xf43f5e,
  transparent: true,
  opacity: 1,
});

/**
 * Computes natural flexible rubber cable catenary curve between two 3D positions.
 * Takes into account gravity sag between layers and natural soft slack within layers.
 */
export function computeFlexibleRubberCurve(
  p1: THREE.Vector3,
  p2: THREE.Vector3
): THREE.QuadraticBezierCurve3 {
  const dist = p1.distanceTo(p2);
  const horizDist = Math.hypot(p2.x - p1.x, p2.z - p1.z);
  const deltaY = p2.y - p1.y;
  const mid = new THREE.Vector3().addVectors(p1, p2).multiplyScalar(0.5);

  if (Math.abs(deltaY) > 1.2) {
    // Inter-layer connection:
    // Flexible rubber cable hangs downward naturally with gravity
    const sag = Math.min(1.2, Math.max(0.25, horizDist * 0.1));
    mid.y = (p1.y + p2.y) * 0.5 - sag;
  } else {
    // Intra-layer connection:
    // Natural flexible rubber arch/slack above the layer floor
    const arcHeight = Math.min(1.8, Math.max(0.35, dist * 0.15));
    mid.y += arcHeight;
  }

  return new THREE.QuadraticBezierCurve3(p1, mid, p2);
}

export class WireRenderer2 {
  private scene: THREE.Scene;
  private envMap: THREE.Texture | null = null;
  private structuralLines: THREE.LineSegments | null = null;
  private importWires: ImportWire[] = [];
  private brokenNodeIds = new Set<string>();
  private isMobile: boolean;

  private sparks: SparkParticle[] = [];
  private wireFadeProgress = 0; // 0 to 1
  private isFadingIn = false;

  constructor(scene: THREE.Scene, isMobile = false, envMap: THREE.Texture | null = null) {
    this.scene = scene;
    this.isMobile = isMobile;
    this.envMap = envMap;
  }

  fadeIn() {
    this.isFadingIn = true;
  }

  setBreakage(brokenNodeIds: Set<string>) {
    this.brokenNodeIds = brokenNodeIds;
    this.importWires.forEach((w) => {
      const isBroken = this.brokenNodeIds.has(w.sourceId) || this.brokenNodeIds.has(w.targetId);
      if (w.isSevered !== isBroken) {
        w.isSevered = isBroken;
        const targetRadius = isBroken ? 0.044 : 0.028;
        w.baseRadius = targetRadius;

        // Rebuild tube geometry with updated thickness
        w.tubeGeo.dispose();
        w.tubeGeo = new THREE.TubeGeometry(w.curve, 32, targetRadius, 8, false);
        w.tubeMesh.geometry = w.tubeGeo;

        if (isBroken) {
          w.tubeMat.color.setHex(0xbe123c);
          w.tubeMat.emissive.setHex(0xf43f5e);
          w.tubeMat.emissiveIntensity = 0.55;
          w.tubeMat.opacity = 0.98 * Math.max(0.1, this.wireFadeProgress);
          w.pulse.materials.forEach((m) => m.color.setHex(0xf43f5e));

          // Spawn severing spark particles at wire midpoint
          this.spawnSeveringSparks(w.curve.getPoint(0.5));
        } else {
          w.tubeMat.color.setHex(0x0f766e);
          w.tubeMat.emissive.setHex(0x14b8a6);
          w.tubeMat.emissiveIntensity = 0.25;
          w.tubeMat.opacity = 0.88 * Math.max(0.1, this.wireFadeProgress);
          w.pulse.materials.forEach((m) => m.color.setHex(0x5eead4));
        }
      }
    });
  }

  private spawnSeveringSparks(pos: THREE.Vector3) {
    const sparkCount = this.isMobile ? 4 : 8;
    for (let i = 0; i < sparkCount; i++) {
      const mesh = new THREE.Mesh(SPARK_GEO, SPARK_MAT.clone());
      mesh.position.copy(pos);
      this.scene.add(mesh);

      const vel = new THREE.Vector3(
        (Math.random() - 0.5) * 3,
        Math.random() * 2.5 + 0.8,
        (Math.random() - 0.5) * 3
      );
      this.sparks.push({
        mesh,
        vel,
        life: 0,
        maxLife: 0.4 + Math.random() * 0.2,
      });
    }
  }

  build(
    folderAnchors: Map<string, LayoutFolderAnchor>,
    nodePositions: Map<string, LayoutNodePosition>,
    edges: AtlasEdge[],
    instantVisible = false
  ) {
    this.clear();
    this.wireFadeProgress = instantVisible ? 1 : 0;
    this.isFadingIn = instantVisible;

    // 1. Structural lines (folder tree hierarchy)
    const structPoints: THREE.Vector3[] = [];

    folderAnchors.forEach((folder) => {
      if (folder.parent !== null) {
        const parent = folderAnchors.get(folder.parent);
        if (parent) {
          structPoints.push(new THREE.Vector3(parent.x, parent.y, parent.z));
          structPoints.push(new THREE.Vector3(folder.x, folder.y, folder.z));
        }
      }
    });

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
        opacity: instantVisible ? 0.12 : 0,
      });
      this.structuralLines = new THREE.LineSegments(structGeo, structMat);
      this.scene.add(this.structuralLines);
    }

    // 2. Import wires with realistic rounded rubber 3D TubeGeometry and comet-trail pulses
    edges.forEach((edge, idx) => {
      const source = nodePositions.get(edge.source);
      const target = nodePositions.get(edge.target);
      if (!source || !target) return;

      const p1 = new THREE.Vector3(source.x, source.y, source.z);
      const p2 = new THREE.Vector3(target.x, target.y, target.z);

      // Compute natural flexible catenary curve
      const curve = computeFlexibleRubberCurve(p1, p2);
      const isBroken = this.brokenNodeIds.has(edge.source) || this.brokenNodeIds.has(edge.target);
      // Realistic rubber wire radius (was 0.008 -> 0.028)
      const radius = isBroken ? 0.044 : 0.028;

      const tubeGeo = new THREE.TubeGeometry(curve, 32, radius, 8, false);
      const tubeMat = new THREE.MeshPhysicalMaterial({
        color: isBroken ? 0xbe123c : 0x0f766e,
        emissive: isBroken ? 0xf43f5e : 0x14b8a6,
        emissiveIntensity: isBroken ? 0.55 : 0.25,
        roughness: 0.42,
        metalness: 0.1,
        clearcoat: 0.35,
        clearcoatRoughness: 0.25,
        envMap: this.envMap,
        transparent: true,
        opacity: (isBroken ? 0.98 : 0.88) * this.wireFadeProgress,
      });
      const tubeMesh = new THREE.Mesh(tubeGeo, tubeMat);
      this.scene.add(tubeMesh);

      // Comet-trail pulse: 1 lead photon sphere + 3 trailing spheres with tapering scale
      const pulseGroup = new THREE.Group();
      const pulseSpheres: THREE.Mesh[] = [];
      const pulseMaterials: THREE.MeshBasicMaterial[] = [];

      for (let s = 0; s < 4; s++) {
        const mat = new THREE.MeshBasicMaterial({
          color: isBroken ? 0xf43f5e : 0x5eead4,
          transparent: true,
          opacity: 0,
        });
        const geo = s === 0 ? LEAD_PULSE_GEO : TRAIL_GEOS[s - 1];
        const sphere = new THREE.Mesh(geo, mat);
        sphere.visible = false;
        pulseGroup.add(sphere);
        pulseSpheres.push(sphere);
        pulseMaterials.push(mat);
      }
      this.scene.add(pulseGroup);

      // Organic stagger: 35% of wires start with packet in-flight, rest in idle cooldown
      const initialProgress =
        Math.random() < 0.35
          ? Math.random() * 0.85
          : -(0.5 + Math.random() * 2.5);

      this.importWires.push({
        id: `${edge.source}->${edge.target}:${idx}`,
        sourceId: edge.source,
        targetId: edge.target,
        curve,
        tubeMesh,
        tubeGeo,
        tubeMat,
        pulse: {
          group: pulseGroup,
          spheres: pulseSpheres,
          materials: pulseMaterials,
        },
        pulseProgress: initialProgress,
        pulseSpeed: 0.35 + Math.random() * 0.25, // packet traverses wire in ~1.6 - 2.4s
        isSevered: isBroken,
        baseRadius: radius,
      });
    });
  }

  updateNodePosition(nodeId: string, x: number, y: number, z: number) {
    this.importWires.forEach((wire) => {
      if (wire.sourceId === nodeId || wire.targetId === nodeId) {
        const p1 = wire.sourceId === nodeId ? new THREE.Vector3(x, y, z) : wire.curve.v0;
        const p2 = wire.targetId === nodeId ? new THREE.Vector3(x, y, z) : wire.curve.v2;

        const updatedCurve = computeFlexibleRubberCurve(p1, p2);
        wire.curve.v0.copy(updatedCurve.v0);
        wire.curve.v1.copy(updatedCurve.v1);
        wire.curve.v2.copy(updatedCurve.v2);

        // Rebuild tube geometry along the moved flexible curve
        wire.tubeGeo.dispose();
        wire.tubeGeo = new THREE.TubeGeometry(wire.curve, 32, wire.baseRadius, 8, false);
        wire.tubeMesh.geometry = wire.tubeGeo;
      }
    });
  }

  update(delta: number) {
    // 1. Coordinated wire opacity fade-in
    if (this.isFadingIn && this.wireFadeProgress < 1) {
      this.wireFadeProgress = Math.min(1, this.wireFadeProgress + delta * 2.5);
      if (this.structuralLines) {
        (this.structuralLines.material as THREE.LineBasicMaterial).opacity =
          0.12 * this.wireFadeProgress;
      }
      this.importWires.forEach((w) => {
        const base = w.isSevered ? 0.98 : 0.88;
        w.tubeMat.opacity = base * this.wireFadeProgress;
      });
    }

    // 2. Realistic photon data packet flow along cables
    const trailOffsets = [0, 0.016, 0.032, 0.048];
    const trailAlphas = [1.0, 0.65, 0.35, 0.15];

    for (let i = 0; i < this.importWires.length; i++) {
      const wire = this.importWires[i];
      if (this.wireFadeProgress < 0.1) {
        wire.pulse.group.visible = false;
        continue;
      }

      // Check if wire packet is in idle cooldown between transmissions
      if (wire.pulseProgress < 0) {
        wire.pulseProgress += delta;
        wire.pulse.group.visible = false;
        continue;
      }

      // Packet is currently in flight along the curve
      wire.pulseProgress += delta * wire.pulseSpeed;

      if (wire.pulseProgress >= 1.0) {
        // Packet arrived at destination card! Enter idle pause before next transmission
        wire.pulseProgress = -(0.8 + Math.random() * 2.4); // 0.8s - 3.2s natural pause
        wire.pulse.group.visible = false;
        continue;
      }

      wire.pulse.group.visible = true;

      // Smooth endpoint envelope: smoothly emit from source card and absorb into target card
      const prog = wire.pulseProgress;
      let envelope = 1.0;
      if (prog < 0.12) {
        envelope = prog / 0.12;
      } else if (prog > 0.88) {
        envelope = (1.0 - prog) / 0.12;
      }

      // Position lead photon sphere and trailing comet spheres along the bezier curve
      for (let s = 0; s < wire.pulse.spheres.length; s++) {
        const trailProg = prog - trailOffsets[s];

        // Never wrap around! If a trailing sphere is not yet on the wire [0, 1], hide it cleanly
        if (trailProg < 0 || trailProg > 1) {
          wire.pulse.spheres[s].visible = false;
        } else {
          wire.pulse.spheres[s].visible = true;
          const pt = wire.curve.getPoint(trailProg);
          wire.pulse.spheres[s].position.copy(pt);
          wire.pulse.materials[s].opacity =
            trailAlphas[s] * envelope * this.wireFadeProgress;
        }
      }
    }

    // 3. Severing spark particles
    for (let i = this.sparks.length - 1; i >= 0; i--) {
      const sp = this.sparks[i];
      sp.life += delta;
      if (sp.life >= sp.maxLife) {
        this.scene.remove(sp.mesh);
        sp.mesh.geometry.dispose();
        (sp.mesh.material as THREE.Material).dispose();
        this.sparks.splice(i, 1);
      } else {
        sp.mesh.position.addScaledVector(sp.vel, delta);
        sp.vel.y -= 9.8 * delta * 0.5; // gravity
        const alpha = 1 - sp.life / sp.maxLife;
        (sp.mesh.material as THREE.MeshBasicMaterial).opacity = alpha;
        sp.mesh.scale.setScalar(Math.max(0.01, alpha));
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
      this.scene.remove(w.tubeMesh);
      w.tubeGeo.dispose();
      w.tubeMat.dispose();

      this.scene.remove(w.pulse.group);
      w.pulse.materials.forEach((m) => m.dispose());
    });
    this.importWires = [];

    this.sparks.forEach((sp) => {
      this.scene.remove(sp.mesh);
      sp.mesh.geometry.dispose();
      (sp.mesh.material as THREE.Material).dispose();
    });
    this.sparks = [];
  }

  dispose() {
    this.clear();
  }
}
