import * as THREE from "three";
import { Spring3 } from "./SpringVector3";

export class CameraRig {
  private camera: THREE.PerspectiveCamera;
  private container: HTMLElement;
  private isReducedMotion: boolean;

  // Orbit state springs
  // x: theta, y: phi, z: radius
  private orbitSpring = new Spring3(120, 22);
  private lookAtSpring = new Spring3(100, 20);

  private isOrbiting = false;
  private isPanning = false;
  private isDragging = false;
  private isSpacePressed = false;

  private defaultRadius = 24;
  private minRadius = 1.5;
  private maxRadius = 120;
  private idleTime = 0;

  private mouseNDC = new THREE.Vector2(0, 0);
  private unsubscribers: Array<() => void> = [];

  constructor(
    camera: THREE.PerspectiveCamera,
    container: HTMLElement,
    isReducedMotion = false
  ) {
    this.camera = camera;
    this.container = container;
    this.isReducedMotion = isReducedMotion;

    // Initial orientation: theta = 0.4, phi = 1.05, radius = 24
    this.orbitSpring.snapTo(0.4, 1.05, 24);
    this.orbitSpring.setTarget(0.4, 1.05, 24);

    this.lookAtSpring.snapTo(0, -3, 0);
    this.lookAtSpring.setTarget(0, -3, 0);

    this.setupListeners();
  }

  init(defaultRadius: number, boundingRadius?: number) {
    this.defaultRadius = defaultRadius;
    if (boundingRadius && boundingRadius > 0) {
      this.maxRadius = Math.max(60, boundingRadius * 6);
    }

    if (this.isReducedMotion) {
      // Direct snap without fly-in animation
      this.orbitSpring.snapTo(0.4, 1.05, defaultRadius);
      this.orbitSpring.setTarget(0.4, 1.05, defaultRadius);
      this.lookAtSpring.snapTo(0, -3, 0);
      this.lookAtSpring.setTarget(0, -3, 0);
    } else {
      // Cinematic intro fly-in: Start at 2.8x radius from high angle
      this.orbitSpring.snapTo(0.4, 0.85, Math.min(this.maxRadius, defaultRadius * 2.8));
      this.orbitSpring.setTarget(0.4, 1.05, defaultRadius);
      this.lookAtSpring.snapTo(0, -3, 0);
      this.lookAtSpring.setTarget(0, -3, 0);
    }
  }

  resetView() {
    this.orbitSpring.setTarget(0.4, 1.05, this.defaultRadius);
    this.lookAtSpring.setTarget(0, -3, 0);
  }

  focus(x: number, y: number, z: number) {
    this.lookAtSpring.setTarget(x, y, z);
    const closeRadius = Math.max(this.minRadius + 2, Math.min(22, this.defaultRadius * 0.5));
    this.orbitSpring.targetZ = closeRadius;
  }

  setIsDragging(dragging: boolean) {
    this.isDragging = dragging;
  }

  private setupListeners() {
    let prevX = 0;
    let prevY = 0;

    const onMouseDown = (e: MouseEvent) => {
      prevX = e.clientX;
      prevY = e.clientY;

      // Pan: middle button (1), right button (2), or left button with Spacebar
      if (e.button === 1 || e.button === 2 || (e.button === 0 && this.isSpacePressed)) {
        this.isPanning = true;
        this.isOrbiting = false;
        e.preventDefault();
      } else if (e.button === 0) {
        // Left click: Orbit
        this.isOrbiting = true;
        this.isPanning = false;
      }
    };

    const onMouseMove = (e: MouseEvent) => {
      // Track normalized device coordinates for zoom-to-cursor
      const rect = this.container.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        this.mouseNDC.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouseNDC.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      }

      if (this.isPanning) {
        const dx = e.clientX - prevX;
        const dy = e.clientY - prevY;
        prevX = e.clientX;
        prevY = e.clientY;

        // Screen-to-world factor at current lookAt distance
        const vFov = (this.camera.fov * Math.PI) / 180;
        const currentR = Math.max(1, this.orbitSpring.z);
        const visibleHeight = 2 * Math.tan(vFov / 2) * currentR;
        const visibleWidth = visibleHeight * this.camera.aspect;
        const factorX = visibleWidth / Math.max(1, rect.width || window.innerWidth);
        const factorY = visibleHeight / Math.max(1, rect.height || window.innerHeight);

        // Camera basis vectors in world space
        const right = new THREE.Vector3();
        const up = new THREE.Vector3();
        this.camera.matrixWorld.extractBasis(right, up, new THREE.Vector3());

        const panOffset = new THREE.Vector3()
          .addScaledVector(right, -dx * factorX)
          .addScaledVector(up, dy * factorY);

        this.lookAtSpring.targetX += panOffset.x;
        this.lookAtSpring.targetY += panOffset.y;
        this.lookAtSpring.targetZ += panOffset.z;
        return;
      }

      if (this.isOrbiting) {
        const dx = e.clientX - prevX;
        const dy = e.clientY - prevY;
        prevX = e.clientX;
        prevY = e.clientY;

        this.orbitSpring.targetX -= dx * 0.005;
        this.orbitSpring.targetY = Math.max(
          0.15,
          Math.min(Math.PI / 2 - 0.05, this.orbitSpring.targetY - dy * 0.005)
        );
      }
    };

    const onMouseUp = () => {
      this.isOrbiting = false;
      this.isPanning = false;
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();

      // Zoom-to-cursor: raycast to horizontal plane at lookAtY
      if (e.deltaY < 0) {
        // Zooming in: gently move lookAt point towards cursor world position
        const raycaster = new THREE.Raycaster();
        raycaster.setFromCamera(this.mouseNDC, this.camera);
        const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -this.lookAtSpring.y);
        const hit = new THREE.Vector3();
        if (raycaster.ray.intersectPlane(plane, hit)) {
          const nudge = 0.12;
          this.lookAtSpring.targetX += (hit.x - this.lookAtSpring.targetX) * nudge;
          this.lookAtSpring.targetZ += (hit.z - this.lookAtSpring.targetZ) * nudge;
        }
      }

      const zoomFactor = e.deltaY * 0.04;
      this.orbitSpring.targetZ = Math.max(
        this.minRadius,
        Math.min(this.maxRadius, this.orbitSpring.targetZ + zoomFactor)
      );
    };

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      if (e.code === "Space") {
        this.isSpacePressed = true;
      } else if (e.code === "KeyF") {
        this.resetView();
      } else if (e.code === "Equal" || e.code === "NumpadAdd") {
        // Zoom in
        this.orbitSpring.targetZ = Math.max(this.minRadius, this.orbitSpring.targetZ - 4);
      } else if (e.code === "Minus" || e.code === "NumpadSubtract") {
        // Zoom out
        this.orbitSpring.targetZ = Math.min(this.maxRadius, this.orbitSpring.targetZ + 4);
      } else if (e.code === "ArrowLeft") {
        this.lookAtSpring.targetX -= 1.5;
      } else if (e.code === "ArrowRight") {
        this.lookAtSpring.targetX += 1.5;
      } else if (e.code === "ArrowUp") {
        this.lookAtSpring.targetY += 1.5;
      } else if (e.code === "ArrowDown") {
        this.lookAtSpring.targetY -= 1.5;
      }
    };

    const onKeyUp = (e: KeyboardEvent) => {
      if (e.code === "Space") {
        this.isSpacePressed = false;
        if (this.isPanning && !this.isOrbiting) {
          this.isPanning = false;
        }
      }
    };

    const onContextMenu = (e: MouseEvent) => {
      // Prevent context menu so right-drag pan is completely smooth
      e.preventDefault();
    };

    // Touch support (pinch to zoom, 2-finger pan, 1-finger orbit)
    let initialTouchDistance = 0;
    let initialTouchRadius = 0;
    let prevTouchX = 0;
    let prevTouchY = 0;

    const onTouchStart = (e: TouchEvent) => {
      if (e.touches.length === 1) {
        prevTouchX = e.touches[0].clientX;
        prevTouchY = e.touches[0].clientY;
        this.isOrbiting = true;
      } else if (e.touches.length === 2) {
        this.isOrbiting = false;
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        initialTouchDistance = Math.hypot(dx, dy);
        initialTouchRadius = this.orbitSpring.targetZ;
        prevTouchX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
        prevTouchY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
      }
    };

    const onTouchMove = (e: TouchEvent) => {
      if (e.touches.length === 1 && this.isOrbiting) {
        const dx = e.touches[0].clientX - prevTouchX;
        const dy = e.touches[0].clientY - prevTouchY;
        prevTouchX = e.touches[0].clientX;
        prevTouchY = e.touches[0].clientY;

        this.orbitSpring.targetX -= dx * 0.006;
        this.orbitSpring.targetY = Math.max(
          0.15,
          Math.min(Math.PI / 2 - 0.05, this.orbitSpring.targetY - dy * 0.006)
        );
      } else if (e.touches.length === 2 && initialTouchDistance > 0) {
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        const dist = Math.hypot(dx, dy);
        const scale = initialTouchDistance / Math.max(1, dist);
        this.orbitSpring.targetZ = Math.max(
          this.minRadius,
          Math.min(this.maxRadius, initialTouchRadius * scale)
        );

        // 2-finger pan
        const midX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
        const midY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
        const panDx = midX - prevTouchX;
        const panDy = midY - prevTouchY;
        prevTouchX = midX;
        prevTouchY = midY;

        const vFov = (this.camera.fov * Math.PI) / 180;
        const visibleHeight = 2 * Math.tan(vFov / 2) * this.orbitSpring.z;
        const factor = visibleHeight / window.innerHeight;

        const right = new THREE.Vector3();
        const up = new THREE.Vector3();
        this.camera.matrixWorld.extractBasis(right, up, new THREE.Vector3());
        this.lookAtSpring.targetX -= (right.x * panDx - up.x * panDy) * factor;
        this.lookAtSpring.targetY -= (right.y * panDx - up.y * panDy) * factor;
        this.lookAtSpring.targetZ -= (right.z * panDx - up.z * panDy) * factor;
      }
    };

    const onTouchEnd = () => {
      this.isOrbiting = false;
      initialTouchDistance = 0;
    };

    this.container.addEventListener("mousedown", onMouseDown);
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    this.container.addEventListener("wheel", onWheel, { passive: false });
    this.container.addEventListener("contextmenu", onContextMenu);
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);

    this.container.addEventListener("touchstart", onTouchStart, { passive: true });
    window.addEventListener("touchmove", onTouchMove, { passive: true });
    window.addEventListener("touchend", onTouchEnd);

    this.unsubscribers.push(() => {
      this.container.removeEventListener("mousedown", onMouseDown);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      this.container.removeEventListener("wheel", onWheel);
      this.container.removeEventListener("contextmenu", onContextMenu);
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
      this.container.removeEventListener("touchstart", onTouchStart);
      window.removeEventListener("touchmove", onTouchMove);
      window.removeEventListener("touchend", onTouchEnd);
    });
  }

  update(dt: number) {
    // 1. Idle parallax drift (subtle live camera feel) when not interacting
    if (!this.isOrbiting && !this.isPanning && !this.isDragging && !this.isReducedMotion) {
      this.idleTime += dt;
      // Very gentle sinusoidal drift (±0.012 rad)
      const driftTheta = Math.sin(this.idleTime * 0.4) * 0.012;
      const driftPhi = Math.cos(this.idleTime * 0.3) * 0.008;
      this.orbitSpring.x += driftTheta * dt;
      this.orbitSpring.y += driftPhi * dt;
    }

    // 2. Spring updates
    this.orbitSpring.update(dt);
    this.lookAtSpring.update(dt);

    const theta = this.orbitSpring.x;
    const phi = Math.max(0.12, Math.min(Math.PI / 2 - 0.03, this.orbitSpring.y));
    const r = Math.max(this.minRadius, this.orbitSpring.z);

    const lookAtX = this.lookAtSpring.x;
    const lookAtY = this.lookAtSpring.y;
    const lookAtZ = this.lookAtSpring.z;

    this.camera.position.set(
      lookAtX + r * Math.sin(phi) * Math.sin(theta),
      lookAtY + r * Math.cos(phi),
      lookAtZ + r * Math.sin(phi) * Math.cos(theta)
    );
    this.camera.lookAt(lookAtX, lookAtY, lookAtZ);
  }

  dispose() {
    this.unsubscribers.forEach((u) => u());
    this.unsubscribers = [];
  }
}
