/**
 * OrganismScene — imperative Three.js scene for the Organism View.
 *
 * Patterns mirror TelexBot3D.tsx exactly:
 *  - ACESFilmicToneMapping, toneMappingExposure=1.35
 *  - PCFSoftShadowMap
 *  - Realistic studio lighting (ambient, key, fill, rim, bounce)
 *  - requestAnimationFrame loop stored in animationFrameId
 *  - Full GPU disposal on destroy()
 *
 * Brand palette:
 *  --void:       #000000
 *  --text-pure:  #FFFFFF
 *  Semantic amber:  #E5A93C  (breaking / generating / in-flux)
 *  Semantic teal:   #5EEAD4  (fixed / verified / pr opened)
 *  NO red/green traffic-light colors.
 */

import * as THREE from "three";
import type { IncidentGraph, IncidentNode } from "./types";
import { OrganismSimulation } from "./OrganismSimulation";
import { NodeRenderer, NODE_STATUS } from "./NodeRenderer";
import { WireRenderer } from "./WireRenderer";

export interface SceneNode {
  id: string;
  x: number;
  y: number;
  z: number;
  vx?: number;
  vy?: number;
  vz?: number;
  meta: IncidentNode;
  resolved?: boolean;
}

export class OrganismScene {
  private renderer!: THREE.WebGLRenderer;
  private scene!: THREE.Scene;
  private camera!: THREE.PerspectiveCamera;
  private animationFrameId = 0;
  private clockTime = 0;
  private simulation!: OrganismSimulation;
  private nodeRenderer!: NodeRenderer;
  private wireRenderer!: WireRenderer;
  private rootMesh!: THREE.Mesh;
  private rootGlowMesh!: THREE.Mesh;
  private isMobile = false;
  private autoRotateAngle = 0;
  private lastInteraction = 0;
  private orbitState = { theta: 0, phi: Math.PI / 4 };
  private targetOrbit = { theta: 0, phi: Math.PI / 4 };
  private cameraRadius = 14;
  private prefersReducedMotion = false;
  private pointerDown: { x: number; y: number } | null = null;

  /** Map from code_usage_id → scene node */
  nodes = new Map<string, SceneNode>();

  constructor(private container: HTMLElement) {}

  init(graph: IncidentGraph) {
    const w = this.container.clientWidth;
    const h = this.container.clientHeight;
    this.isMobile = window.matchMedia("(max-width: 768px)").matches;
    this.prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

    // ── Renderer ───────────────────────────────────────────────────────────
    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: "high-performance",
    });
    this.renderer.setSize(w, h);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.35;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.container.appendChild(this.renderer.domElement);

    // ── Scene ──────────────────────────────────────────────────────────────
    this.scene = new THREE.Scene();
    this.scene.fog = new THREE.FogExp2(0x000000, 0.025);

    // ── Camera ─────────────────────────────────────────────────────────────
    this.cameraRadius = this.isMobile ? 20 : 14;
    this.camera = new THREE.PerspectiveCamera(42, w / h, 0.1, 200);
    this._updateCamera();

    // ── Studio Lighting (matches TelexBot3D.tsx exactly) ──────────────────
    this.scene.add(new THREE.AmbientLight(0xffffff, 1.4));

    const keyLight = new THREE.DirectionalLight(0xffffff, 2.8);
    keyLight.position.set(8, 10, 8);
    keyLight.castShadow = true;
    this.scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0xdde5f0, 1.2);
    fillLight.position.set(-8, 4, 6);
    this.scene.add(fillLight);

    const rimLight = new THREE.DirectionalLight(0xffffff, 2.0);
    rimLight.position.set(0, 8, -8);
    this.scene.add(rimLight);

    const bounceLight = new THREE.DirectionalLight(0xffffff, 0.5);
    bounceLight.position.set(0, -8, 4);
    this.scene.add(bounceLight);

    // ── Root Node (fixed at origin) ────────────────────────────────────────
    const rootGeo = new THREE.IcosahedronGeometry(1.0, 2);
    const rootMat = new THREE.MeshPhysicalMaterial({
      color: 0xe5a93c,
      emissive: 0xe5a93c,
      emissiveIntensity: 0.7,
      roughness: 0.15,
      metalness: 0.6,
      clearcoat: 0.8,
    });
    this.rootMesh = new THREE.Mesh(rootGeo, rootMat);
    this.rootMesh.castShadow = true;
    this.scene.add(this.rootMesh);

    // Glow duplicate (additive blending, no postprocessing bloom)
    const rootGlowGeo = new THREE.IcosahedronGeometry(1.35, 1);
    const rootGlowMat = new THREE.MeshBasicMaterial({
      color: 0xe5a93c,
      transparent: true,
      opacity: 0.08,
      blending: THREE.AdditiveBlending,
      side: THREE.BackSide,
      depthWrite: false,
    });
    this.rootGlowMesh = new THREE.Mesh(rootGlowGeo, rootGlowMat);
    this.scene.add(this.rootGlowMesh);

    // ── Sub-systems ────────────────────────────────────────────────────────
    this.simulation = new OrganismSimulation();
    this.nodeRenderer = new NodeRenderer(this.scene);
    this.wireRenderer = new WireRenderer(this.scene);

    // Hydrate existing nodes from snapshot
    for (const node of graph.nodes) {
      this._addNode(node);
    }

    // ── Input ──────────────────────────────────────────────────────────────
    this._bindInput();

    // ── Animation Loop ─────────────────────────────────────────────────────
    this._startLoop();
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  addNode(node: IncidentNode) {
    if (this.nodes.has(node.code_usage_id)) {
      this.updateNodeStatus(node.code_usage_id, node.status);
      return;
    }
    this._addNode(node);
  }

  updateNodeStatus(id: string, status: string) {
    const sn = this.nodes.get(id);
    if (!sn) return;
    sn.meta = { ...sn.meta, status };
    const vizStatus = this._statusToViz(status);
    this.nodeRenderer.setStatus(id, vizStatus);
  }

  updateNodeValidation(id: string, passed: boolean) {
    const sn = this.nodes.get(id);
    if (!sn) return;
    sn.meta = { ...sn.meta, status: passed ? "patched" : "failed" };
    this.nodeRenderer.setStatus(id, passed ? NODE_STATUS.VERIFIED : NODE_STATUS.FAILED);
  }

  setPulse(id: string, direction: "out" | "in") {
    this.wireRenderer.addPulse(id, direction, this.clockTime);
  }

  resolveNode(id: string) {
    const sn = this.nodes.get(id);
    if (!sn) return;
    sn.resolved = true;
    this.nodeRenderer.setStatus(id, NODE_STATUS.RESOLVED);
  }

  triggerSceneAmbience() {
    // brief whole-scene pulse — used for job_running/done events
    (this.rootMesh.material as THREE.MeshPhysicalMaterial).emissiveIntensity = 1.6;
    setTimeout(() => {
      if (!this.rootMesh) return;
      (this.rootMesh.material as THREE.MeshPhysicalMaterial).emissiveIntensity = 0.7;
    }, 400);
  }

  destroy() {
    cancelAnimationFrame(this.animationFrameId);
    this._unbindInput();
    this.nodeRenderer.dispose();
    this.wireRenderer.dispose();
    this.scene.traverse((obj) => {
      if (obj instanceof THREE.Mesh) {
        obj.geometry.dispose();
        const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
        mats.forEach((m) => m.dispose());
      }
    });
    this.renderer.dispose();
    if (this.container.contains(this.renderer.domElement)) {
      this.container.removeChild(this.renderer.domElement);
    }
  }

  // ── Private ─────────────────────────────────────────────────────────────────

  private _addNode(node: IncidentNode) {
    const simNode = this.simulation.addNode(node.code_usage_id, node.line_end - node.line_start);
    const sn: SceneNode = {
      id: node.code_usage_id,
      x: simNode.x,
      y: simNode.y,
      z: simNode.z,
      meta: node,
      resolved: node.status === "patched",
    };
    this.nodes.set(node.code_usage_id, sn);
    const radius = Math.max(0.3, Math.min(1.2, (node.line_end - node.line_start) / 80));
    this.nodeRenderer.add(node.code_usage_id, radius, this._statusToViz(node.status));
    this.wireRenderer.add(node.code_usage_id);
  }

  private _statusToViz(status: string): number {
    switch (status) {
      case "patched":     return NODE_STATUS.VERIFIED;
      case "failed":      return NODE_STATUS.FAILED;
      case "pending":     return NODE_STATUS.ACTIVE;
      default:            return NODE_STATUS.DORMANT;
    }
  }

  private _updateCamera() {
    const r = this.cameraRadius;
    this.camera.position.set(
      r * Math.sin(this.orbitState.theta) * Math.sin(this.orbitState.phi),
      r * Math.cos(this.orbitState.phi),
      r * Math.cos(this.orbitState.theta) * Math.sin(this.orbitState.phi)
    );
    this.camera.lookAt(0, 0, 0);
    this.camera.updateProjectionMatrix();
  }

  private _startLoop() {
    const tick = () => {
      this.animationFrameId = requestAnimationFrame(tick);
      this.clockTime += 0.016;

      // ── Physics tick ────────────────────────────────────────────────
      if (!this.prefersReducedMotion) {
        this.simulation.tick();
      }

      // ── Auto-rotate when idle ────────────────────────────────────────
      const idleSec = (Date.now() - this.lastInteraction) / 1000;
      if (!this.prefersReducedMotion && idleSec > 4) {
        this.autoRotateAngle += 0.003;
        this.targetOrbit.theta = this.autoRotateAngle;
      }

      // Smooth camera lerp
      this.orbitState.theta += (this.targetOrbit.theta - this.orbitState.theta) * 0.05;
      this.orbitState.phi   += (this.targetOrbit.phi   - this.orbitState.phi)   * 0.05;
      this._updateCamera();

      // ── Root pulse ───────────────────────────────────────────────────
      const rootPulse = !this.prefersReducedMotion
        ? 0.7 + Math.sin(this.clockTime * 2.4) * 0.15
        : 0.7;
      (this.rootMesh.material as THREE.MeshPhysicalMaterial).emissiveIntensity = rootPulse;
      this.rootMesh.rotation.y += 0.006;
      this.rootMesh.rotation.x += 0.003;
      this.rootGlowMesh.rotation.y -= 0.004;

      // ── Sync node meshes to simulation positions ─────────────────────
      for (const [id, sn] of this.nodes) {
        const simPos = this.simulation.getPosition(id);
        if (!simPos) continue;
        // Drift resolved nodes outward
        const targetDist = sn.resolved ? 8 : 4.5;
        const len = Math.sqrt(simPos.x**2 + simPos.y**2 + simPos.z**2) || 1;
        const t = 0.02;
        sn.x += (simPos.x / len * targetDist - sn.x) * t + sn.x * 0.0001;
        sn.y += (simPos.y / len * targetDist - sn.y) * t;
        sn.z += (simPos.z / len * targetDist - sn.z) * t;

        this.nodeRenderer.setPosition(id, sn.x, sn.y, sn.z);
        this.wireRenderer.setNodePosition(id, sn.x, sn.y, sn.z);
      }

      // ── Wire pulses ──────────────────────────────────────────────────
      this.wireRenderer.tick(this.clockTime, this.prefersReducedMotion);

      this.renderer.render(this.scene, this.camera);
    };
    tick();
  }

  // ── Input handlers ──────────────────────────────────────────────────────────

  private _handlePointerDown = (e: PointerEvent) => {
    this.lastInteraction = Date.now();
    this.autoRotateAngle = this.orbitState.theta;
    this.pointerDown = { x: e.clientX, y: e.clientY };
  };

  private _handlePointerMove = (e: PointerEvent) => {
    if (!this.pointerDown) return;
    const dx = e.clientX - this.pointerDown.x;
    const dy = e.clientY - this.pointerDown.y;
    this.pointerDown = { x: e.clientX, y: e.clientY };
    this.targetOrbit.theta -= dx * 0.008;
    this.targetOrbit.phi = Math.max(0.3, Math.min(Math.PI - 0.3, this.targetOrbit.phi - dy * 0.008));
    this.lastInteraction = Date.now();
  };

  private _handlePointerUp = () => { this.pointerDown = null; };

  private _handleWheel = (e: WheelEvent) => {
    e.preventDefault();
    this.cameraRadius = Math.max(8, Math.min(30, this.cameraRadius + e.deltaY * 0.02));
    this.lastInteraction = Date.now();
  };

  private _handleResize = () => {
    const w = this.container.clientWidth;
    const h = this.container.clientHeight;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  };

  private _bindInput() {
    const el = this.renderer.domElement;
    el.addEventListener("pointerdown", this._handlePointerDown);
    el.addEventListener("pointermove", this._handlePointerMove);
    el.addEventListener("pointerup", this._handlePointerUp);
    el.addEventListener("wheel", this._handleWheel, { passive: false });
    window.addEventListener("resize", this._handleResize);
  }

  private _unbindInput() {
    const el = this.renderer.domElement;
    el.removeEventListener("pointerdown", this._handlePointerDown);
    el.removeEventListener("pointermove", this._handlePointerMove);
    el.removeEventListener("pointerup", this._handlePointerUp);
    el.removeEventListener("wheel", this._handleWheel);
    window.removeEventListener("resize", this._handleResize);
  }
}
