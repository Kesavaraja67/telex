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
  private isDragging = false;
  private defaultRadius = 24;
  private idleTime = 0;

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

  init(defaultRadius: number) {
    this.defaultRadius = defaultRadius;

    if (this.isReducedMotion) {
      // Direct snap without fly-in animation
      this.orbitSpring.snapTo(0.4, 1.05, defaultRadius);
      this.orbitSpring.setTarget(0.4, 1.05, defaultRadius);
      this.lookAtSpring.snapTo(0, -3, 0);
      this.lookAtSpring.setTarget(0, -3, 0);
    } else {
      // Cinematic intro fly-in: Start at 2.8x radius from high angle
      this.orbitSpring.snapTo(0.4, 0.85, defaultRadius * 2.8);
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
    const closeRadius = Math.max(8, Math.min(22, this.defaultRadius * 0.5));
    this.orbitSpring.targetZ = closeRadius;
  }

  setIsDragging(dragging: boolean) {
    this.isDragging = dragging;
  }

  private setupListeners() {
    let prevX = 0;
    let prevY = 0;

    const onMouseDown = (e: MouseEvent) => {
      // Allow orbit on background click (middle/right or left click on empty canvas)
      if (e.button === 0 || e.button === 1 || e.button === 2) {
        this.isOrbiting = true;
        prevX = e.clientX;
        prevY = e.clientY;
      }
    };

    const onMouseMove = (e: MouseEvent) => {
      if (!this.isOrbiting) return;
      const dx = e.clientX - prevX;
      const dy = e.clientY - prevY;
      prevX = e.clientX;
      prevY = e.clientY;

      this.orbitSpring.targetX -= dx * 0.005;
      this.orbitSpring.targetY = Math.max(
        0.15,
        Math.min(Math.PI / 2 - 0.05, this.orbitSpring.targetY - dy * 0.005)
      );
    };

    const onMouseUp = () => {
      this.isOrbiting = false;
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const zoomFactor = e.deltaY * 0.04;
      this.orbitSpring.targetZ = Math.max(
        6,
        Math.min(120, this.orbitSpring.targetZ + zoomFactor)
      );
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

  update(dt: number) {
    // 1. Idle parallax drift (subtle live camera feel) when not interacting
    if (!this.isOrbiting && !this.isDragging && !this.isReducedMotion) {
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
    const r = Math.max(4, this.orbitSpring.z);

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
