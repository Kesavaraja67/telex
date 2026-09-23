import * as THREE from "three";
import type { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import type { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";

import type { AtlasGraphPayload, AtlasNode, AtlasSelection } from "./types";
import { LayeredLayout, type LayoutFolderAnchor, type LayoutNodePosition, CARD_WIDTH, CARD_HEIGHT } from "./LayeredLayout";
import { CardTextureAtlas } from "./CardTextureAtlas";
import { WireRenderer2 } from "./WireRenderer2";
import { DragController } from "./DragController";
import { subscribeLastEdited } from "./lastEditedCache";
import { prefersReducedMotion } from "@/lib/animations";

import { buildPostProcessing } from "./render/PostProcessing";
import { buildAtmosphereField } from "./render/AtmosphereField";
import { Spring3 } from "./render/SpringVector3";
import { getSharedEnvMap, createCardMaterial, createContactShadowMesh } from "./render/CardMaterial";
import { EntranceDirector, type EntranceTarget } from "./render/EntranceDirector";
import { CameraRig } from "./render/CameraRig";

export interface AtlasSceneOptions {
  onSelect: (selection: AtlasSelection) => void;
  repoId?: string;
  commitSha?: string;
}

interface CardMeshEntry {
  nodeId: string;
  node: AtlasNode;
  mesh: THREE.Mesh;
  shadowMesh: THREE.Mesh;
  baseX: number;
  baseY: number;
  baseZ: number;
  currentX: number;
  currentY: number;
  currentZ: number;
  isHovered: boolean;
  isDragging: boolean;
  isReturning: boolean;
  isSelected: boolean;
  isBroken: boolean;
  lastEditedText?: string;
  texture?: THREE.CanvasTexture;
  mat: THREE.MeshPhysicalMaterial;
  liftSpring: Spring3;
  posSpring: Spring3;
  tiltXSpring: Spring3;
  tiltZSpring: Spring3;
  resolveFlashTimer: number;
}

export class AtlasScene {
  private container: HTMLElement;
  private opts: AtlasSceneOptions;

  private scene: THREE.Scene;
  private camera: THREE.PerspectiveCamera;
  private renderer: THREE.WebGLRenderer;
  private composer: EffectComposer;
  private bloomPass: UnrealBloomPass;
  private animationFrameId: number | null = null;
  private clock = new THREE.Clock();

  private isMobile = false;
  private isReducedMotion = false;
  private brokenNodeIds = new Set<string>();
  private breakageMap = new Map<string, string[]>();

  private cards = new Map<string, CardMeshEntry>();
  private folderObjects: THREE.Object3D[] = [];

  private envMap: THREE.Texture;
  private atmosphereField: THREE.Points;
  private cameraRig: CameraRig;
  private wireRenderer: WireRenderer2;
  private dragController: DragController;
  private entranceDirector: EntranceDirector | null = null;
  private entranceDone = false;
  private totalTime = 0;

  private defaultRadius = 24;
  private selectedNodeId: string | null = null;
  private unsubscribers: Array<() => void> = [];
  private onWindowResize: () => void;

  constructor(container: HTMLElement, opts: AtlasSceneOptions) {
    this.container = container;
    this.opts = opts;

    if (typeof window !== "undefined") {
      this.isMobile = window.matchMedia("(max-width: 768px)").matches;
      this.isReducedMotion = prefersReducedMotion();
    }

    const width = container.clientWidth || window.innerWidth;
    const height = container.clientHeight || window.innerHeight;

    // 1. Scene with atmospheric fog (receding depth cues in pure black void)
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x000000);
    this.scene.fog = new THREE.FogExp2(0x000000, 0.018);

    // 2. Camera
    this.camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);

    // 3. Renderer with ACESFilmicToneMapping & shadow map
    this.renderer = new THREE.WebGLRenderer({
      antialias: !this.isMobile,
      powerPreference: "high-performance",
    });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, this.isMobile ? 1.5 : 2));
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.35;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    container.appendChild(this.renderer.domElement);

    // 4. Procedural studio env map baked once via PMREM
    this.envMap = getSharedEnvMap(this.renderer);

    // 5. Post-processing pipeline (EffectComposer + Bloom)
    const { composer, bloom } = buildPostProcessing(
      this.renderer,
      this.scene,
      this.camera,
      width,
      height,
      this.isMobile
    );
    this.composer = composer;
    this.bloomPass = bloom;

    // 6. Atmosphere ambient particles field
    this.atmosphereField = buildAtmosphereField(this.isMobile);
    this.scene.add(this.atmosphereField);

    // 7. Lighting Rig (ambient + key + fill + rim)
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.85);
    this.scene.add(ambientLight);

    const keyLight = new THREE.DirectionalLight(0xffffff, 1.2);
    keyLight.position.set(15, 25, 20);
    this.scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0xffffff, 0.35);
    fillLight.position.set(-15, 10, -15);
    this.scene.add(fillLight);

    const rimLight = new THREE.DirectionalLight(0xffffff, 0.6);
    rimLight.position.set(0, -20, -20);
    this.scene.add(rimLight);

    // 8. Wire Renderer with physical studio lighting
    this.wireRenderer = new WireRenderer2(this.scene, this.isMobile, this.envMap);

    // 9. Camera Rig with spring physics, idle parallax, and cinematic fly-in
    this.cameraRig = new CameraRig(this.camera, this.container, this.isReducedMotion);

    // 10. Drag & Interaction Controller
    this.dragController = new DragController(
      this.container,
      this.camera,
      {
        onHover: this.handleHover.bind(this),
        onSelect: this.handleSelect.bind(this),
        onDragStart: this.handleDragStart.bind(this),
        onDrag: this.handleDrag.bind(this),
        onDragEnd: this.handleDragEnd.bind(this),
      },
      this.isMobile
    );

    // 11. Resize handling
    this.onWindowResize = () => {
      const w = this.container.clientWidth || window.innerWidth;
      const h = this.container.clientHeight || window.innerHeight;
      if (w === 0 || h === 0) return;
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(w, h);
      this.composer.setSize(w, h);
    };
    window.addEventListener("resize", this.onWindowResize);

    if (typeof ResizeObserver !== "undefined") {
      const ro = new ResizeObserver(() => {
        this.onWindowResize();
      });
      ro.observe(this.container);
      this.unsubscribers.push(() => ro.disconnect());
    }

    // 12. Start render loop
    this.animate();
  }

  init(data: AtlasGraphPayload) {
    const layout = LayeredLayout.compute(data.graph);

    // 1. Build folder anchors
    this.buildFolderAnchors(layout.folderAnchors);

    // 2. Build cards
    this.buildCards(layout.nodePositions);

    // 3. Build wires
    this.wireRenderer.build(
      layout.folderAnchors,
      layout.nodePositions,
      data.graph.edges,
      this.isReducedMotion
    );

    // 4. Calculate default camera radius based on repository node scale (expanded for spacious layout)
    const nodeCount = data.graph.nodes.length;
    this.defaultRadius = Math.max(26, Math.min(85, 24 + Math.sqrt(nodeCount) * 1.8));
    this.cameraRig.init(this.defaultRadius);

    // 5. Staggered hierarchical entrance director
    const entranceTargets: EntranceTarget[] = [];
    let maxDepth = 0;

    this.cards.forEach((c) => {
      const depth = c.node.depth || 0;
      if (depth > maxDepth) maxDepth = depth;
      entranceTargets.push({
        mesh: c.mesh,
        material: c.mat,
        depth,
      });
    });

    this.entranceDirector = new EntranceDirector(
      entranceTargets,
      maxDepth,
      this.isReducedMotion
    );

    if (this.isReducedMotion) {
      this.entranceDone = true;
      this.wireRenderer.fadeIn();
    }
  }

  resetView() {
    this.cameraRig.resetView();
  }

  focusNode(nodeId: string) {
    const card = this.cards.get(nodeId);
    if (!card) return;
    this.cameraRig.focus(card.baseX, card.baseY, card.baseZ);
  }

  setBreakage(breakage: Map<string, string[]> | Set<string>) {
    if (breakage instanceof Map) {
      this.breakageMap = breakage;
      this.brokenNodeIds = new Set(breakage.keys());
    } else {
      this.brokenNodeIds = breakage;
      this.breakageMap = new Map(Array.from(breakage).map((id) => [id, []]));
    }
    this.wireRenderer.setBreakage(this.brokenNodeIds);

    this.cards.forEach((card, id) => {
      const isBroken = this.brokenNodeIds.has(id);
      if (card.isBroken !== isBroken) {
        const wasBroken = card.isBroken;
        card.isBroken = isBroken;
        this.refreshCardTexture(card);

        if (isBroken) {
          card.mat.emissive.setHex(0xe11d48);
          card.mat.emissiveIntensity = 0.28;
        } else if (wasBroken) {
          // Transitioned from broken to resolved: trigger brief white resolve pulse
          card.resolveFlashTimer = 0.6;
          card.mat.emissive.setHex(0xffffff);
          card.mat.emissiveIntensity = 0.35;
        }
      }
    });
  }

  private buildFolderAnchors(folderAnchors: Map<string, LayoutFolderAnchor>) {
    const torusGeo = new THREE.TorusGeometry(1.6, 0.025, 16, 32);
    torusGeo.rotateX(Math.PI / 2);

    const torusMat = new THREE.MeshBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.14,
    });

    folderAnchors.forEach((folder) => {
      if (!folder.id) return;

      const group = new THREE.Group();
      group.position.set(folder.x, folder.y, folder.z);

      // Ring
      const ring = new THREE.Mesh(torusGeo, torusMat);
      group.add(ring);

      // High-res floating folder label (512x128 retina texture)
      const labelCanvas = document.createElement("canvas");
      labelCanvas.width = 512;
      labelCanvas.height = 128;
      const ctx = labelCanvas.getContext("2d")!;

      ctx.fillStyle = "rgba(161, 161, 170, 0.9)";
      ctx.font = "600 36px monospace, ui-monospace";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(`[ ${folder.name} ]`, 256, 64);

      const labelTex = new THREE.CanvasTexture(labelCanvas);
      labelTex.minFilter = THREE.LinearFilter;
      labelTex.magFilter = THREE.LinearFilter;
      const spriteMat = new THREE.SpriteMaterial({ map: labelTex, transparent: true });
      const sprite = new THREE.Sprite(spriteMat);
      sprite.scale.set(3.0, 0.75, 1);
      sprite.position.set(0, 0.55, 0);
      group.add(sprite);

      this.scene.add(group);
      this.folderObjects.push(group);
    });
  }

  private buildCards(nodePositions: Map<string, LayoutNodePosition>) {
    const planeGeo = new THREE.PlaneGeometry(CARD_WIDTH, CARD_HEIGHT);
    const cardMeshMap = new Map<string, THREE.Object3D>();

    nodePositions.forEach((pos, id) => {
      const tex = CardTextureAtlas.createCardTexture(pos.node);
      const mat = createCardMaterial(tex, this.envMap);

      const mesh = new THREE.Mesh(planeGeo, mat);
      mesh.position.set(pos.x, pos.y, pos.z);
      // Face slightly toward default camera angle
      mesh.rotation.x = -0.15;
      this.scene.add(mesh);
      cardMeshMap.set(id, mesh);

      // Soft contact shadow underneath card
      const shadowMesh = createContactShadowMesh(CARD_WIDTH, CARD_HEIGHT);
      shadowMesh.position.set(pos.x, pos.y - 0.01, pos.z);
      this.scene.add(shadowMesh);

      const entry: CardMeshEntry = {
        nodeId: id,
        node: pos.node,
        mesh,
        shadowMesh,
        baseX: pos.x,
        baseY: pos.y,
        baseZ: pos.z,
        currentX: pos.x,
        currentY: pos.y,
        currentZ: pos.z,
        isHovered: false,
        isDragging: false,
        isReturning: false,
        isSelected: false,
        isBroken: this.brokenNodeIds.has(id),
        texture: tex,
        mat,
        liftSpring: new Spring3(180, 24),
        posSpring: new Spring3(175, 18),
        tiltXSpring: new Spring3(140, 20),
        tiltZSpring: new Spring3(140, 20),
        resolveFlashTimer: 0,
      };
      entry.posSpring.snapTo(pos.x, 0, pos.z);

      if (entry.isBroken) {
        entry.mat.emissive.setHex(0xe11d48);
        entry.mat.emissiveIntensity = 0.28;
      }

      this.cards.set(id, entry);

      // Subscribe to lazy last-edited commit metadata
      if (this.opts.repoId) {
        const unsub = subscribeLastEdited(
          this.opts.repoId,
          pos.node.id,
          this.opts.commitSha || "HEAD",
          (data) => {
            if (data.value && entry.lastEditedText !== data.value) {
              entry.lastEditedText = data.value;
              this.refreshCardTexture(entry);
            }
          }
        );
        this.unsubscribers.push(unsub);
      }
    });

    this.dragController.setTargets(cardMeshMap);
  }

  private refreshCardTexture(entry: CardMeshEntry) {
    if (entry.texture) entry.texture.dispose();
    entry.texture = CardTextureAtlas.createCardTexture(
      entry.node,
      entry.lastEditedText,
      entry.isBroken,
      entry.isSelected
    );
    entry.mat.map = entry.texture;
    entry.mat.needsUpdate = true;
  }

  private handleHover(nodeId: string | null) {
    this.cards.forEach((card, id) => {
      const hovered = id === nodeId;
      if (card.isHovered !== hovered) {
        card.isHovered = hovered;
        if (!card.isDragging) {
          card.liftSpring.setTarget(0, hovered ? 0.22 : 0, 0);
          if (hovered && !this.isReducedMotion) {
            card.tiltXSpring.setTarget(0.04, 0, 0);
          } else {
            card.tiltXSpring.setTarget(0, 0, 0);
            card.tiltZSpring.setTarget(0, 0, 0);
          }
        }
      }
    });
  }

  private handleSelect(nodeId: string) {
    this.selectedNodeId = nodeId;
    const card = this.cards.get(nodeId);
    if (!card) return;

    this.cards.forEach((c) => {
      const wasSelected = c.isSelected;
      c.isSelected = c.nodeId === nodeId;
      if (wasSelected !== c.isSelected) {
        this.refreshCardTexture(c);
      }
    });

    const brokenBy = card.isBroken ? this.breakageMap.get(nodeId) || [] : [];

    this.opts.onSelect({
      nodeId,
      brokenBy,
      node: card.node,
    });
  }

  private handleDragStart(nodeId: string) {
    const card = this.cards.get(nodeId);
    if (card) {
      card.isDragging = true;
      card.isReturning = false;
      card.liftSpring.setTarget(0, 0.38, 0);
      card.posSpring.snapTo(card.mesh.position.x, 0, card.mesh.position.z);
      this.cameraRig.setIsDragging(true);
    }
  }

  private handleDrag(nodeId: string, x: number, y: number, z: number) {
    const card = this.cards.get(nodeId);
    if (card) {
      card.currentX = x;
      card.currentZ = z;
      card.mesh.position.x = x;
      card.mesh.position.z = z;
      card.shadowMesh.position.x = x;
      card.shadowMesh.position.z = z;
      card.posSpring.snapTo(x, 0, z);
      this.wireRenderer.updateNodePosition(nodeId, x, card.baseY, z);
    }
  }

  private handleDragEnd(nodeId: string) {
    const card = this.cards.get(nodeId);
    if (card) {
      card.isDragging = false;
      card.isReturning = true;
      // Smoothly spring back to its original home position!
      card.posSpring.setTarget(card.baseX, 0, card.baseZ);
      card.liftSpring.setTarget(0, 0, 0);
      card.tiltXSpring.setTarget(0, 0, 0);
      card.tiltZSpring.setTarget(0, 0, 0);
      this.cameraRig.setIsDragging(false);
    }
  }

  private animate() {
    this.animationFrameId = requestAnimationFrame(this.animate.bind(this));
    const delta = Math.min(0.08, this.clock.getDelta());
    this.totalTime += delta;

    // 1. Camera rig spring update
    this.cameraRig.update(delta);

    // 2. Atmosphere particle drift
    if (this.atmosphereField) {
      this.atmosphereField.position.y -= delta * 0.03;
      if (this.atmosphereField.position.y < -25) {
        this.atmosphereField.position.y = 5;
      }
    }

    // 3. Staggered entrance director
    if (this.entranceDirector && !this.entranceDone) {
      const done = this.entranceDirector.update(delta);
      if (done) {
        this.entranceDone = true;
        this.wireRenderer.fadeIn();
      }
    }

    // 4. Card springs, contact shadows, and breathing broken glow
    this.cards.forEach((card) => {
      card.liftSpring.update(delta);
      card.tiltXSpring.update(delta);
      card.tiltZSpring.update(delta);

      if (card.isReturning) {
        card.posSpring.update(delta);
        card.mesh.position.x = card.posSpring.x;
        card.mesh.position.z = card.posSpring.z;
        card.currentX = card.posSpring.x;
        card.currentZ = card.posSpring.z;
        card.shadowMesh.position.x = card.posSpring.x;
        card.shadowMesh.position.z = card.posSpring.z;

        // Dynamically stretch and snap attached rubber wires during return
        this.wireRenderer.updateNodePosition(
          card.nodeId,
          card.posSpring.x,
          card.baseY,
          card.posSpring.z
        );

        // Check if settled back at base position
        const distToBase = Math.hypot(
          card.posSpring.x - card.baseX,
          card.posSpring.z - card.baseZ
        );
        if (distToBase < 0.004) {
          card.isReturning = false;
          card.mesh.position.x = card.baseX;
          card.mesh.position.z = card.baseZ;
          card.currentX = card.baseX;
          card.currentZ = card.baseZ;
          card.shadowMesh.position.x = card.baseX;
          card.shadowMesh.position.z = card.baseZ;
          card.posSpring.snapTo(card.baseX, 0, card.baseZ);
          this.wireRenderer.updateNodePosition(
            card.nodeId,
            card.baseX,
            card.baseY,
            card.baseZ
          );
        }
      }

      card.mesh.position.y = card.baseY + card.liftSpring.y;
      card.mesh.rotation.x = -0.15 + card.tiltXSpring.x;
      card.mesh.rotation.z = card.tiltZSpring.z;

      // Contact shadow opacity tied to lift height
      const shadowMat = card.shadowMesh.material as THREE.MeshBasicMaterial;
      const liftRatio = Math.max(0, Math.min(1, card.liftSpring.y / 0.38));
      shadowMat.opacity = liftRatio * 0.52;
      card.shadowMesh.position.x = card.mesh.position.x;
      card.shadowMesh.position.z = card.mesh.position.z;

      // Broken-state breathing glow
      if (card.isBroken) {
        if (this.isReducedMotion) {
          card.mat.emissiveIntensity = 0.28;
        } else {
          // Sinusoidal breathing pulse (~1.6s period)
          const pulse = 0.16 + 0.18 * (0.5 + 0.5 * Math.sin(this.totalTime * 3.8));
          card.mat.emissiveIntensity = pulse;
        }
      } else if (card.resolveFlashTimer > 0) {
        // Incident resolved teal pulse decay
        card.resolveFlashTimer -= delta;
        const ratio = Math.max(0, card.resolveFlashTimer / 0.6);
        card.mat.emissiveIntensity = ratio * 0.35;
        if (card.resolveFlashTimer <= 0) {
          card.mat.emissiveIntensity = 0;
          card.mat.emissive.setHex(0x000000);
        }
      }
    });

    // 5. Wire pulses and sparks
    this.wireRenderer.update(delta);

    // 6. Post-processing render pass (EffectComposer with bloom)
    this.composer.render();
  }

  destroy() {
    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
    }
    window.removeEventListener("resize", this.onWindowResize);
    this.unsubscribers.forEach((u) => u());
    this.cameraRig.dispose();
    this.dragController.dispose();
    this.wireRenderer.dispose();

    this.cards.forEach((card) => {
      this.scene.remove(card.mesh);
      card.mesh.geometry.dispose();
      card.mat.dispose();
      if (card.texture) card.texture.dispose();

      this.scene.remove(card.shadowMesh);
      card.shadowMesh.geometry.dispose();
      (card.shadowMesh.material as THREE.Material).dispose();
    });
    this.cards.clear();

    this.folderObjects.forEach((obj) => {
      this.scene.remove(obj);
      obj.traverse((child) => {
        if (child instanceof THREE.Mesh) {
          child.geometry.dispose();
          if (Array.isArray(child.material)) {
            child.material.forEach((m) => m.dispose());
          } else {
            child.material.dispose();
          }
        }
      });
    });
    this.folderObjects = [];

    if (this.atmosphereField) {
      this.scene.remove(this.atmosphereField);
      this.atmosphereField.geometry.dispose();
      (this.atmosphereField.material as THREE.Material).dispose();
    }

    this.renderer.dispose();
    if (this.renderer.domElement.parentElement) {
      this.renderer.domElement.parentElement.removeChild(this.renderer.domElement);
    }
  }
}
