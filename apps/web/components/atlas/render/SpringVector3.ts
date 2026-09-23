export class Spring3 {
  x = 0;
  y = 0;
  z = 0;
  vx = 0;
  vy = 0;
  vz = 0;
  targetX = 0;
  targetY = 0;
  targetZ = 0;

  constructor(private stiffness = 170, private damping = 26) {}

  setTarget(x: number, y: number, z: number) {
    this.targetX = x;
    this.targetY = y;
    this.targetZ = z;
  }

  snapTo(x: number, y: number, z: number) {
    this.x = this.targetX = x;
    this.y = this.targetY = y;
    this.z = this.targetZ = z;
    this.vx = this.vy = this.vz = 0;
  }

  update(dt: number) {
    // Clamp delta time to avoid instability on huge frame drops
    const clampedDt = Math.min(0.05, Math.max(0.001, dt));
    const step = (pos: number, vel: number, target: number): [number, number] => {
      const force = (target - pos) * this.stiffness - vel * this.damping;
      const newVel = vel + force * clampedDt;
      const newPos = pos + newVel * clampedDt;
      return [newPos, newVel];
    };
    [this.x, this.vx] = step(this.x, this.vx, this.targetX);
    [this.y, this.vy] = step(this.y, this.vy, this.targetY);
    [this.z, this.vz] = step(this.z, this.vz, this.targetZ);
  }
}
