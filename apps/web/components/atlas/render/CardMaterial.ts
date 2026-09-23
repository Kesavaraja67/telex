import * as THREE from "three";

let sharedEnvMap: THREE.Texture | null = null;
let sharedShadowTex: THREE.CanvasTexture | null = null;

/**
 * Procedural studio environment map baked once via PMREMGenerator.
 * Creates realistic clearcoat reflections without loading external HDRI files.
 */
export function getSharedEnvMap(renderer: THREE.WebGLRenderer): THREE.Texture {
  if (sharedEnvMap) return sharedEnvMap;

  const pmrem = new THREE.PMREMGenerator(renderer);
  const envScene = new THREE.Scene();

  // Dark spherical backdrop
  const grad = new THREE.Mesh(
    new THREE.SphereGeometry(50, 16, 16),
    new THREE.MeshBasicMaterial({
      side: THREE.BackSide,
      color: 0x0a0a0c,
    })
  );
  envScene.add(grad);

  // Soft studio lighting panels
  const panelMat1 = new THREE.MeshBasicMaterial({ color: 0x3a3a40 });
  const panel1 = new THREE.Mesh(new THREE.PlaneGeometry(20, 20), panelMat1);
  panel1.position.set(15, 20, 10);
  panel1.lookAt(0, 0, 0);
  envScene.add(panel1);

  const panelMat2 = new THREE.MeshBasicMaterial({ color: 0x143a36 });
  const panel2 = new THREE.Mesh(new THREE.PlaneGeometry(15, 15), panelMat2);
  panel2.position.set(-15, 5, -10);
  panel2.lookAt(0, 0, 0);
  envScene.add(panel2);

  sharedEnvMap = pmrem.fromScene(envScene, 0.04).texture;
  pmrem.dispose();
  return sharedEnvMap;
}

export function createCardMaterial(
  tex: THREE.CanvasTexture,
  envMap: THREE.Texture
): THREE.MeshPhysicalMaterial {
  return new THREE.MeshPhysicalMaterial({
    map: tex,
    transparent: true,
    roughness: 0.22,
    metalness: 0.06,
    clearcoat: 0.35,
    clearcoatRoughness: 0.25,
    envMap,
    envMapIntensity: 0.5,
    emissive: new THREE.Color(0x000000),
    emissiveIntensity: 0,
  });
}

/**
 * Shared soft contact-shadow radial gradient texture.
 */
export function getSharedShadowTexture(): THREE.CanvasTexture {
  if (sharedShadowTex) return sharedShadowTex;

  const c = document.createElement("canvas");
  c.width = 128;
  c.height = 128;
  const ctx = c.getContext("2d")!;
  const grad = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
  grad.addColorStop(0, "rgba(0, 0, 0, 0.55)");
  grad.addColorStop(1, "rgba(0, 0, 0, 0)");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, 128, 128);

  sharedShadowTex = new THREE.CanvasTexture(c);
  return sharedShadowTex;
}

export function createContactShadowMesh(cardWidth: number, cardHeight: number): THREE.Mesh {
  const geo = new THREE.PlaneGeometry(cardWidth * 1.5, cardHeight * 1.5);
  // Lay flat in X/Z plane
  geo.rotateX(-Math.PI / 2);
  const mat = new THREE.MeshBasicMaterial({
    map: getSharedShadowTexture(),
    transparent: true,
    opacity: 0,
    depthWrite: false,
  });
  return new THREE.Mesh(geo, mat);
}
