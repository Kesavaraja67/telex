import * as THREE from "three";
import type { AtlasGraphPayload, AtlasNode, AtlasSelection } from "./types";
import { LayeredLayout, type LayoutFolderAnchor, type LayoutNodePosition, CARD_WIDTH, CARD_HEIGHT } from "./LayeredLayout";
import { CardTextureAtlas } from "./CardTextureAtlas";
import { WireRenderer2 } from "./WireRenderer2";
import { DragController } from "./DragController";
import { subscribeLastEdited } from "./lastEditedCache";

export interface AtlasSceneOptions {
  onSelect: (selection: AtlasSelection) => void;
  repoId?: string;
  commitSha?: string;
}

interface CardMeshEntry {
  nodeId: string;
  node: AtlasNode;
  mesh: THREE.Mesh;
  glowMesh?: THREE.Mesh;
  baseY: number;
  currentX: number;
  currentY: number;
  currentZ: number;
  isHovered: boolean;
  isDragging: boolean;
  isSelected: boolean;
  isBroken: boolean;
  lastEditedText?: string;
  texture?: THREE.CanvasTexture;
  mat: THREE.MeshPhysicalMaterial;
}

export class AtlasScene {
  private container: HTMLElement;
  private opts: AtlasSceneOptions;

  private scene: THREE.Scene;
  private camera: THREE.PerspectiveCamera;
  private renderer: THREE.WebGLRenderer;
  private animationFrameId: number | null = null;
  private clock = new THREE.Clock();

  private isMobile = false;
  private brokenNodeIds = new Set<string>();
  private breakageMap = new Map<string, string[]>();

  private cards = new Map<string, CardMeshEntry>();
  private folderObjects: THREE.Object3D[] = [];

  private wireRenderer: WireRenderer2;
  private dragController: DragController;

  // Orbit camera state
  private isOrbiting = false;
  private orbitTheta = 0.4;
  private orbitPhi = 1.05;
  private targetTheta = 0.4;
  private targetPhi = 1.05;
  private cameraRadius = 24;
  private targetRadius = 24;
  private defaultRadius = 24;
  private cameraLookAt = new THREE.Vector3(0, -3, 0);
  private targetLookAt = new THREE.Vector3(0, -3, 0);

  private selectedNodeId: string | null = null;
  private unsubscribers: Array<() => void> = [];
  private onWindowResize: () => void;

  constructor(container: HTMLElement, opts: AtlasSceneOptions) {
    this.container = container;
    this.opts = opts;

    if (typeof window !== "undefined") {
      this.isMobile = window.matchMedia("(max-width: 768px)").matches;
    }

    const width = container.clientWidth || window.innerWidth;
    const height = container.clientHeight || window.innerHeight;

    this.onWindowResize = () => {
      const w = this.container.clientWidth || window.innerWidth;
      const h = this.container.clientHeight || window.innerHeight;
      if (w === 0 || h === 0) return;
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(w, h);
    };
    window.addEventListener("resize", this.onWindowResize);

    if (typeof ResizeObserver !== "undefined") {
      const ro = new ResizeObserver(() => {
        this.onWindowResize();
      });
      ro.observe(this.container);
      this.unsubscribers.push(() => ro.disconnect());
    }

    // 1. Scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x000000);

    // 2. Camera
    this.camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    this.updateCameraPosition();

    // 3. Renderer with ACESFilmicToneMapping
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

    // 4. Lighting Rig (ambient + key + fill + rim + bounce)
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.85);
    this.scene.add(ambientLight);

    const keyLight = new THREE.DirectionalLight(0xffffff, 1.2);
    keyLight.position.set(15, 25, 20);
    this.scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0x5eead4, 0.4);
    fillLight.position.set(-15, 10, -15);
    this.scene.add(fillLight);

    const rimLight = new THREE.DirectionalLight(0xffffff, 0.6);
    rimLight.position.set(0, -20, -20);
    this.scene.add(rimLight);

    // 5. Wire Renderer
    this.wireRenderer = new WireRenderer2(this.scene, this.isMobile);

    // 6. Drag & Interaction Controller
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

    // 7. Orbit listeners on canvas
    this.setupOrbitControls();

    // 8. Start render loop
    this.animate();
  }

  init(data: AtlasGraphPayload) {
    const layout = LayeredLayout.compute(data.graph);

    // 1. Build folder anchors
    this.buildFolderAnchors(layout.folderAnchors);

    // 2. Build cards
    this.buildCards(layout.nodePositions);

    // 3. Build wires
    this.wireRenderer.build(layout.folderAnchors, layout.nodePositions, data.graph.edges);

    // Adjust camera radius based on repo scale
    const nodeCount = data.graph.nodes.length;
    this.cameraRadius = Math.max(18, Math.min(65, 16 + Math.sqrt(nodeCount) * 1.3));
    this.targetRadius = this.cameraRadius;
    this.defaultRadius = this.cameraRadius;
    this.updateCameraPosition();
  }

  resetView() {
    this.targetTheta = 0.4;
    this.targetPhi = 1.05;
    this.targetRadius = this.defaultRadius;
    this.targetLookAt.set(0, -3, 0);
  }

  focusNode(nodeId: string) {
    const card = this.cards.get(nodeId);
    if (!card) return;
    this.targetLookAt.set(card.currentX, card.currentY, card.currentZ);
    this.targetRadius = Math.max(8, Math.min(20, this.defaultRadius * 0.5));
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
        card.isBroken = isBroken;
        this.refreshCardTexture(card);
      }
    });
  }

  private buildFolderAnchors(folderAnchors: Map<string, LayoutFolderAnchor>) {
    const torusGeo = new THREE.TorusGeometry(1.2, 0.02, 16, 32);
    torusGeo.rotateX(Math.PI / 2); // Lay flat in X/Z plane

    const torusMat = new THREE.MeshBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.15,
    });

    folderAnchors.forEach((folder) => {
      if (!folder.id) return; // Skip invisible virtual root

      const group = new THREE.Group();
      group.position.set(folder.x, folder.y, folder.z);

      // Ring
      const ring = new THREE.Mesh(torusGeo, torusMat);
      group.add(ring);

      // Floating folder label
      const labelCanvas = document.createElement("canvas");
      labelCanvas.width = 256;
      labelCanvas.height = 64;
      const ctx = labelCanvas.getContext("2d")!;
      ctx.fillStyle = "rgba(161, 161, 170, 0.85)";
      ctx.font = "bold 24px monospace, ui-monospace";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(folder.name, 128, 32);

      const labelTex = new THREE.CanvasTexture(labelCanvas);
      const spriteMat = new THREE.SpriteMaterial({ map: labelTex, transparent: true });
      const sprite = new THREE.Sprite(spriteMat);
      sprite.scale.set(2.4, 0.6, 1);
      sprite.position.set(0, 0.5, 0);
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
      const mat = new THREE.MeshPhysicalMaterial({
        map: tex,
        transparent: true,
        roughness: 0.25,
        metalness: 0.05,
        clearcoat: 0.2,
      });

      const mesh = new THREE.Mesh(planeGeo, mat);
      mesh.position.set(pos.x, pos.y, pos.z);
      // Face slightly toward camera default angle
      mesh.rotation.x = -0.15;

      this.scene.add(mesh);
      cardMeshMap.set(id, mesh);

      const entry: CardMeshEntry = {
        nodeId: id,
        node: pos.node,
        mesh,
        baseY: pos.y,
        currentX: pos.x,
        currentY: pos.y,
        currentZ: pos.z,
        isHovered: false,
        isDragging: false,
        isSelected: false,
        isBroken: this.brokenNodeIds.has(id),
        texture: tex,
        mat,
      };

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
          card.mesh.position.y = card.baseY + (hovered ? 0.2 : 0);
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

    const brokenBy = card.isBroken
      ? this.breakageMap.get(nodeId) || []
      : [];

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
      card.mesh.position.y = card.baseY + 0.35; // Lift up while dragging
    }
  }

  private handleDrag(nodeId: string, x: number, y: number, z: number) {
    const card = this.cards.get(nodeId);
    if (card) {
      card.currentX = x;
      card.currentZ = z;
      card.mesh.position.x = x;
      card.mesh.position.z = z;
      // Y stays locked to card's layer depth
      card.mesh.position.y = card.baseY + 0.35;
      this.wireRenderer.updateNodePosition(nodeId, x, card.baseY, z);
    }
  }

  private handleDragEnd(nodeId: string) {
    const card = this.cards.get(nodeId);
    if (card) {
      card.isDragging = false;
      card.mesh.position.y = card.baseY; // Return to layer resting Y
    }
  }

  private setupOrbitControls() {
    let prevX = 0;
    let prevY = 0;

    const onMouseDown = (e: MouseEvent) => {
      // Left click on empty space or middle/right click
      if (e.target !== this.renderer.domElement) return;
      this.isOrbiting = true;
      prevX = e.clientX;
      prevY = e.clientY;
    };

    const onMouseMove = (e: MouseEvent) => {
      if (!this.isOrbiting) return;
      const dx = e.clientX - prevX;
      const dy = e.clientY - prevY;
      prevX = e.clientX;
      prevY = e.clientY;

      this.targetTheta -= dx * 0.005;
      this.targetPhi = Math.max(0.15, Math.min(Math.PI / 2 - 0.05, this.targetPhi - dy * 0.005));
    };

    const onMouseUp = () => {
      this.isOrbiting = false;
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      this.targetRadius = Math.max(6, Math.min(120, this.targetRadius + e.deltaY * 0.04));
    };

    this.container.addEventListener("mousedown", onMouseDown);
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    this.container.addEventListener("wheel", onWheel, { passive: false });

    this.unsubscribers.push(() => {
      this.container.removeEventListener("mousedown", onMouseDown);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      this.container.removeEventListener("wheel", onWheel);
    });
  }

  private updateCameraPosition() {
    const r = this.cameraRadius;
    this.camera.position.set(
      this.cameraLookAt.x + r * Math.sin(this.orbitPhi) * Math.sin(this.orbitTheta),
      this.cameraLookAt.y + r * Math.cos(this.orbitPhi),
      this.cameraLookAt.z + r * Math.sin(this.orbitPhi) * Math.cos(this.orbitTheta)
    );
    this.camera.lookAt(this.cameraLookAt);
  }

  private animate() {
    this.animationFrameId = requestAnimationFrame(this.animate.bind(this));
    const delta = Math.min(0.1, this.clock.getDelta());

    // Camera damping
    this.orbitTheta += (this.targetTheta - this.orbitTheta) * 0.1;
    this.orbitPhi += (this.targetPhi - this.orbitPhi) * 0.1;
    this.cameraRadius += (this.targetRadius - this.cameraRadius) * 0.1;
    this.cameraLookAt.lerp(this.targetLookAt, 0.1);
    this.updateCameraPosition();

    // Wire pulse animation
    this.wireRenderer.update(delta);

    this.renderer.render(this.scene, this.camera);
  }

  destroy() {
    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
    }
    window.removeEventListener("resize", this.onWindowResize);
    this.unsubscribers.forEach((u) => u());
    this.dragController.dispose();
    this.wireRenderer.dispose();

    this.cards.forEach((card) => {
      this.scene.remove(card.mesh);
      card.mesh.geometry.dispose();
      card.mat.dispose();
      if (card.texture) card.texture.dispose();
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

    this.renderer.dispose();
    if (this.renderer.domElement.parentElement) {
      this.renderer.domElement.parentElement.removeChild(this.renderer.domElement);
    }
  }
}
