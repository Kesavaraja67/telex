declare module "d3-force-3d" {
  export function forceSimulation(nodes?: any[], numDimensions?: number): any;
  export function forceCollide(radius?: number | ((d: any) => number)): any;
  export function forceX(x?: number | ((d: any) => number)): any;
  export function forceY(y?: number | ((d: any) => number)): any;
  export function forceZ(z?: number | ((d: any) => number)): any;
  export function forceManyBody(): any;
  export function forceLink(links?: any[]): any;
  export function forceCenter(x?: number, y?: number, z?: number): any;
}
