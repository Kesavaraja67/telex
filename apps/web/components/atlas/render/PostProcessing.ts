import * as THREE from "three";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";

export function buildPostProcessing(
  renderer: THREE.WebGLRenderer,
  scene: THREE.Scene,
  camera: THREE.PerspectiveCamera,
  width: number,
  height: number,
  isMobile: boolean
) {
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));

  // Bloom is what makes the teal/red emissive wire pulses and broken-card glow
  // read as "glowing" rather than flat-colored.
  const bloom = new UnrealBloomPass(
    new THREE.Vector2(width, height),
    isMobile ? 0.55 : 0.85, // strength
    0.4,                     // radius
    isMobile ? 0.72 : 0.62   // threshold (selective so dark background stays pure black)
  );
  composer.addPass(bloom);
  composer.addPass(new OutputPass());

  return { composer, bloom };
}
