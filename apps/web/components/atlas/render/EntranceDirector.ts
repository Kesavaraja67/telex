import * as THREE from "three";

export interface EntranceTarget {
  mesh: THREE.Object3D;
  material: THREE.Material & { opacity?: number };
  depth: number;
}

export class EntranceDirector {
  private elapsed = 0;
  private done = false;

  constructor(
    private targets: EntranceTarget[],
    private maxDepth: number,
    private isReducedMotion = false,
    private durationPerLayer = 0.22,
    private layerStagger = 0.09
  ) {
    if (this.isReducedMotion) {
      // Instant reveal for reduced-motion preference
      targets.forEach((t) => {
        t.mesh.scale.setScalar(1);
        if (t.material.opacity !== undefined) t.material.opacity = 1;
      });
      this.done = true;
    } else {
      targets.forEach((t) => {
        t.mesh.scale.setScalar(0.001);
        if (t.material.opacity !== undefined) t.material.opacity = 0;
      });
    }
  }

  update(dt: number): boolean {
    if (this.done) return true;
    this.elapsed += dt;
    let allDone = true;

    for (const t of this.targets) {
      const startAt = t.depth * this.layerStagger;
      const local = (this.elapsed - startAt) / this.durationPerLayer;
      if (local < 0) {
        allDone = false;
        continue;
      }
      const p = Math.min(1, local);
      // ease-out-back for subtle, physical overshoot settle
      const eased = 1 + 2.7 * Math.pow(p - 1, 3) + 1.7 * Math.pow(p - 1, 2);
      t.mesh.scale.setScalar(Math.max(0.001, eased));
      if (t.material.opacity !== undefined) {
        t.material.opacity = Math.min(1, p * 1.4);
      }
      if (p < 1) allDone = false;
    }

    if (allDone) {
      this.done = true;
      // Ensure all targets end exactly at scale 1
      this.targets.forEach((t) => {
        t.mesh.scale.setScalar(1);
      });
    }
    return allDone;
  }
}
