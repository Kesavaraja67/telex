import * as THREE from "three";

export interface DragControllerCallbacks {
  onHover: (nodeId: string | null) => void;
  onSelect: (nodeId: string) => void;
  onDragStart: (nodeId: string) => void;
  onDrag: (nodeId: string, x: number, y: number, z: number) => void;
  onDragEnd: (nodeId: string) => void;
}

export class DragController {
  private domElement: HTMLElement;
  private camera: THREE.PerspectiveCamera;
  private raycaster = new THREE.Raycaster();
  private mouse = new THREE.Vector2();
  private callbacks: DragControllerCallbacks;

  private targets: THREE.Object3D[] = [];
  private meshToNodeId = new Map<THREE.Object3D, string>();
  private nodeIdToMesh = new Map<string, THREE.Object3D>();

  private isDragging = false;
  private draggedNodeId: string | null = null;
  private draggedPlaneY = 0;
  private dragPlane = new THREE.Plane();
  private planeIntersect = new THREE.Vector3();

  private pointerDownPos = new THREE.Vector2();
  private pointerDownTime = 0;
  private longPressTimer: ReturnType<typeof setTimeout> | null = null;
  private isLongPressActive = false;
  private isMobile = false;

  private boundOnPointerDown: (e: PointerEvent) => void;
  private boundOnPointerMove: (e: PointerEvent) => void;
  private boundOnPointerUp: (e: PointerEvent) => void;

  constructor(
    domElement: HTMLElement,
    camera: THREE.PerspectiveCamera,
    callbacks: DragControllerCallbacks,
    isMobile = false
  ) {
    this.domElement = domElement;
    this.camera = camera;
    this.callbacks = callbacks;
    this.isMobile = isMobile;

    this.boundOnPointerDown = this.onPointerDown.bind(this);
    this.boundOnPointerMove = this.onPointerMove.bind(this);
    this.boundOnPointerUp = this.onPointerUp.bind(this);

    this.domElement.addEventListener("pointerdown", this.boundOnPointerDown);
    window.addEventListener("pointermove", this.boundOnPointerMove);
    window.addEventListener("pointerup", this.boundOnPointerUp);
  }

  setTargets(cardMeshes: Map<string, THREE.Object3D>) {
    this.targets = [];
    this.meshToNodeId.clear();
    this.nodeIdToMesh.clear();

    cardMeshes.forEach((mesh, id) => {
      this.targets.push(mesh);
      this.meshToNodeId.set(mesh, id);
      this.nodeIdToMesh.set(id, mesh);
    });
  }

  private updateMouse(e: PointerEvent) {
    const rect = this.domElement.getBoundingClientRect();
    this.mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
  }

  private onPointerDown(e: PointerEvent) {
    if (e.button !== 0 && e.pointerType === "mouse") return;
    this.updateMouse(e);
    this.pointerDownPos.set(e.clientX, e.clientY);
    this.pointerDownTime = Date.now();
    this.isLongPressActive = false;

    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersects = this.raycaster.intersectObjects(this.targets, false);

    if (intersects.length > 0) {
      const hitMesh = intersects[0].object;
      const nodeId = this.meshToNodeId.get(hitMesh);

      if (nodeId) {
        if (this.isMobile) {
          // Mobile: Require long-press to pick up a card
          this.longPressTimer = setTimeout(() => {
            this.isLongPressActive = true;
            this.startDrag(nodeId, hitMesh.position.y);
          }, 380);
        } else {
          // Desktop: Prepare for drag if mouse moves > 5px
          this.draggedNodeId = nodeId;
          this.draggedPlaneY = hitMesh.position.y;
        }
      }
    }
  }

  private startDrag(nodeId: string, planeY: number) {
    this.isDragging = true;
    this.draggedNodeId = nodeId;
    this.draggedPlaneY = planeY;
    // Plane is horizontal locked to card's exact layer Y
    this.dragPlane.set(new THREE.Vector3(0, 1, 0), -this.draggedPlaneY);
    this.callbacks.onDragStart(nodeId);
  }

  private onPointerMove(e: PointerEvent) {
    this.updateMouse(e);
    const dist = Math.hypot(e.clientX - this.pointerDownPos.x, e.clientY - this.pointerDownPos.y);

    if (dist > 8 && this.longPressTimer) {
      clearTimeout(this.longPressTimer);
      this.longPressTimer = null;
    }

    if (!this.isDragging) {
      // Desktop: Start drag once threshold exceeded
      if (!this.isMobile && this.draggedNodeId && dist > 5) {
        this.startDrag(this.draggedNodeId, this.draggedPlaneY);
      } else {
        // Hover raycast on desktop
        if (!this.isMobile) {
          this.raycaster.setFromCamera(this.mouse, this.camera);
          const intersects = this.raycaster.intersectObjects(this.targets, false);
          if (intersects.length > 0) {
            const hitId = this.meshToNodeId.get(intersects[0].object) || null;
            this.callbacks.onHover(hitId);
          } else {
            this.callbacks.onHover(null);
          }
        }
        return;
      }
    }

    // Active drag handling in horizontal X/Z plane
    if (this.isDragging && this.draggedNodeId) {
      this.raycaster.setFromCamera(this.mouse, this.camera);
      if (this.raycaster.ray.intersectPlane(this.dragPlane, this.planeIntersect)) {
        // Y stays strictly fixed to card's layer depth
        this.callbacks.onDrag(
          this.draggedNodeId,
          this.planeIntersect.x,
          this.draggedPlaneY,
          this.planeIntersect.z
        );
      }
    }
  }

  private onPointerUp(e: PointerEvent) {
    if (this.longPressTimer) {
      clearTimeout(this.longPressTimer);
      this.longPressTimer = null;
    }

    const dist = Math.hypot(e.clientX - this.pointerDownPos.x, e.clientY - this.pointerDownPos.y);
    const duration = Date.now() - this.pointerDownTime;

    if (this.isDragging && this.draggedNodeId) {
      this.callbacks.onDragEnd(this.draggedNodeId);
      this.isDragging = false;
      this.draggedNodeId = null;
    } else if (dist <= 6 && duration < 500) {
      // Clean click / tap without dragging
      this.updateMouse(e);
      this.raycaster.setFromCamera(this.mouse, this.camera);
      const intersects = this.raycaster.intersectObjects(this.targets, false);
      if (intersects.length > 0) {
        const hitId = this.meshToNodeId.get(intersects[0].object);
        if (hitId) {
          this.callbacks.onSelect(hitId);
        }
      }
      this.draggedNodeId = null;
    } else {
      this.draggedNodeId = null;
    }
  }

  dispose() {
    if (this.longPressTimer) clearTimeout(this.longPressTimer);
    this.domElement.removeEventListener("pointerdown", this.boundOnPointerDown);
    window.removeEventListener("pointermove", this.boundOnPointerMove);
    window.removeEventListener("pointerup", this.boundOnPointerUp);
    this.targets = [];
    this.meshToNodeId.clear();
    this.nodeIdToMesh.clear();
  }
}
