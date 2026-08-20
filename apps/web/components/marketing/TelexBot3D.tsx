"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

interface TelexBot3DProps {
  className?: string;
  isScanning?: boolean;
}

export default function TelexBot3D({
  className = "",
}: TelexBot3DProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mousePos = useRef({ x: 0, y: 0, targetX: 0, targetY: 0 });

  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight;

    // 1. Scene, Camera, Renderer
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(34, width / height, 0.1, 1000);
    // Camera positioned back to scale the model down perfectly inside the frame
    camera.position.set(0, -0.05, 8.8);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.35;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(renderer.domElement);

    // 2. Realistic Studio Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 2.0);
    scene.add(ambientLight);

    const keyLight = new THREE.DirectionalLight(0xffffff, 3.2);
    keyLight.position.set(5, 6, 6);
    keyLight.castShadow = true;
    scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0xdde5f0, 1.8);
    fillLight.position.set(-6, 2, 5);
    scene.add(fillLight);

    const rimLight = new THREE.DirectionalLight(0xffffff, 3.5);
    rimLight.position.set(0, 5, -5);
    scene.add(rimLight);

    const bounceLight = new THREE.DirectionalLight(0xffffff, 0.8);
    bounceLight.position.set(0, -5, 3);
    scene.add(bounceLight);

    // 3. Head Master Group (All parts turn with cursor)
    const headGroup = new THREE.Group();
    headGroup.position.set(0, 0.25, 0);
    scene.add(headGroup);

    // Outer Monitor Casing (Warm Vintage Off-White with Soft Shallow Chamfer)
    const casingMat = new THREE.MeshPhysicalMaterial({
      color: 0xdfd9ce,
      roughness: 0.28,
      metalness: 0.08,
      clearcoat: 0.4,
      clearcoatRoughness: 0.2,
      reflectivity: 0.6,
    });

    const mainBoxGeo = new THREE.BoxGeometry(2.75, 2.35, 2.0, 16, 16, 16);
    const monitorCase = new THREE.Mesh(mainBoxGeo, casingMat);
    headGroup.add(monitorCase);

    // Front Bezel Trim (Dark Charcoal Frame)
    const bezelGeo = new THREE.BoxGeometry(2.77, 2.37, 0.08);
    const bezelMat = new THREE.MeshStandardMaterial({
      color: 0x2e2e30,
      roughness: 0.3,
      metalness: 0.75,
    });
    const bezel = new THREE.Mesh(bezelGeo, bezelMat);
    bezel.position.set(0, 0, 1.0);
    headGroup.add(bezel);

    // Lower Brushed Metal Aluminum Faceplate
    const panelGeo = new THREE.BoxGeometry(2.55, 0.42, 0.04);
    const panelMat = new THREE.MeshStandardMaterial({
      color: 0x8a8a8e,
      roughness: 0.3,
      metalness: 0.85,
    });
    const panel = new THREE.Mesh(panelGeo, panelMat);
    panel.position.set(0, -0.85, 1.05);
    headGroup.add(panel);

    // Rotary Control Knobs & LED on Faceplate
    const knobGeo = new THREE.CylinderGeometry(0.09, 0.09, 0.1, 20);
    const knobMat = new THREE.MeshStandardMaterial({ color: 0x1f1f1f, metalness: 0.9, roughness: 0.2 });

    const knob1 = new THREE.Mesh(knobGeo, knobMat);
    knob1.rotation.x = Math.PI / 2;
    knob1.position.set(0.35, -0.85, 1.1);
    headGroup.add(knob1);

    const knob2 = new THREE.Mesh(knobGeo, knobMat);
    knob2.rotation.x = Math.PI / 2;
    knob2.position.set(0.7, -0.85, 1.1);
    headGroup.add(knob2);

    const ledGeo = new THREE.SphereGeometry(0.03, 16, 16);
    const ledMat = new THREE.MeshBasicMaterial({ color: 0x5eead4 });
    const led = new THREE.Mesh(ledGeo, ledMat);
    led.position.set(0.98, -0.85, 1.08);
    headGroup.add(led);

    // 4. Rectangular Flat CRT Screen with Live Canvas Terminal Diff
    const screenCanvas = document.createElement("canvas");
    screenCanvas.width = 1024;
    screenCanvas.height = 768;
    const ctx = screenCanvas.getContext("2d")!;
    const screenTexture = new THREE.CanvasTexture(screenCanvas);

    const screenGeo = new THREE.PlaneGeometry(2.45, 1.45);
    const screenMat = new THREE.MeshBasicMaterial({
      map: screenTexture,
    });
    const screenMesh = new THREE.Mesh(screenGeo, screenMat);
    screenMesh.position.set(0, 0.22, 1.05);
    headGroup.add(screenMesh);

    // High-Gloss Protective Glass Cover (Specular Studio Reflections)
    const glassGeo = new THREE.PlaneGeometry(2.46, 1.46);
    const glassMat = new THREE.MeshPhysicalMaterial({
      color: 0x000000,
      transmission: 0.92,
      opacity: 1,
      transparent: true,
      roughness: 0.05,
      ior: 1.5,
      clearcoat: 1.0,
      clearcoatRoughness: 0.05,
      reflectivity: 0.85,
    });
    const glassMesh = new THREE.Mesh(glassGeo, glassMat);
    glassMesh.position.set(0, 0.22, 1.06);
    headGroup.add(glassMesh);

    // 5. Clean Titanium Neck & Base Pedestal
    const baseGroup = new THREE.Group();
    scene.add(baseGroup);

    const neckGeo = new THREE.CylinderGeometry(0.42, 0.58, 0.75, 32);
    const neckMat = new THREE.MeshStandardMaterial({
      color: 0x222224,
      roughness: 0.3,
      metalness: 0.85,
    });
    const neck = new THREE.Mesh(neckGeo, neckMat);
    neck.position.set(0, -1.25, 0);
    baseGroup.add(neck);

    const collarGeo = new THREE.CylinderGeometry(0.85, 1.15, 0.45, 32);
    const collarMat = new THREE.MeshStandardMaterial({
      color: 0x141416,
      roughness: 0.45,
      metalness: 0.75,
    });
    const collar = new THREE.Mesh(collarGeo, collarMat);
    collar.position.set(0, -1.75, 0);
    baseGroup.add(collar);

    // 6. Complete Jet-Black Cables (Seamlessly Connecting Monitor to Base Collar)
    const cableMat = new THREE.MeshStandardMaterial({
      color: 0x050505,
      roughness: 0.35,
      metalness: 0.15,
    });

    // Left Cable 1
    const curveL1 = new THREE.CatmullRomCurve3([
      new THREE.Vector3(-1.38, -0.2, 0.2),
      new THREE.Vector3(-1.72, -0.75, 0.3),
      new THREE.Vector3(-1.25, -1.45, 0.15),
      new THREE.Vector3(-0.7, -1.72, 0.1),
    ]);
    const cableL1 = new THREE.Mesh(new THREE.TubeGeometry(curveL1, 32, 0.048, 12, false), cableMat);
    headGroup.add(cableL1);

    // Left Cable 2
    const curveL2 = new THREE.CatmullRomCurve3([
      new THREE.Vector3(-1.38, -0.5, 0.35),
      new THREE.Vector3(-1.85, -1.05, 0.45),
      new THREE.Vector3(-1.3, -1.6, 0.25),
      new THREE.Vector3(-0.6, -1.76, 0.15),
    ]);
    const cableL2 = new THREE.Mesh(new THREE.TubeGeometry(curveL2, 32, 0.052, 12, false), cableMat);
    headGroup.add(cableL2);

    // Right Cable 1
    const curveR1 = new THREE.CatmullRomCurve3([
      new THREE.Vector3(1.38, -0.2, 0.2),
      new THREE.Vector3(1.72, -0.75, 0.3),
      new THREE.Vector3(1.25, -1.45, 0.15),
      new THREE.Vector3(0.7, -1.72, 0.1),
    ]);
    const cableR1 = new THREE.Mesh(new THREE.TubeGeometry(curveR1, 32, 0.048, 12, false), cableMat);
    headGroup.add(cableR1);

    // Right Cable 2
    const curveR2 = new THREE.CatmullRomCurve3([
      new THREE.Vector3(1.38, -0.5, 0.35),
      new THREE.Vector3(1.85, -1.05, 0.45),
      new THREE.Vector3(1.3, -1.6, 0.25),
      new THREE.Vector3(0.6, -1.76, 0.15),
    ]);
    const cableR2 = new THREE.Mesh(new THREE.TubeGeometry(curveR2, 32, 0.052, 12, false), cableMat);
    headGroup.add(cableR2);

    // 7. Mouse Movement Listener
    const handleMouseMove = (e: MouseEvent) => {
      const x = (e.clientX / window.innerWidth) * 2 - 1;
      const y = -(e.clientY / window.innerHeight) * 2 + 1;
      mousePos.current.targetX = x;
      mousePos.current.targetY = y;
    };
    window.addEventListener("mousemove", handleMouseMove);

    // 8. Animation & Screen Draw Loop (Calibrated Slower, Smooth Weighted Physics)
    let animationFrameId: number;
    let clockTime = 0;
    let cursorBlink = 0;

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      clockTime += 0.016;

      // Slower Lerp Damping (Silky weighted tracking)
      mousePos.current.x += (mousePos.current.targetX - mousePos.current.x) * 0.035;
      mousePos.current.y += (mousePos.current.targetY - mousePos.current.y) * 0.035;

      // Smooth Gentle Head Rotation
      headGroup.rotation.y = mousePos.current.x * 0.38;
      headGroup.rotation.x = -mousePos.current.y * 0.28 + Math.sin(clockTime * 1.0) * 0.01;
      headGroup.rotation.z = -mousePos.current.x * 0.06;
      headGroup.position.y = 0.25 + Math.sin(clockTime * 1.1) * 0.015;

      // Subtle Base Sway
      baseGroup.rotation.y = mousePos.current.x * 0.08;

      // Gentle Specular Shift
      keyLight.position.x = 5 + mousePos.current.x * 1.8;
      keyLight.position.y = 6 + mousePos.current.y * 1.5;

      // Render Dynamic Terminal Code Diff Screen
      cursorBlink += 0.016;
      const showCursor = Math.floor(cursorBlink * 3) % 2 === 0;

      // 1. Dark CRT Screen Background
      ctx.fillStyle = "#0c1015";
      ctx.fillRect(0, 0, 1024, 768);

      // 2. CRT Scanlines
      ctx.fillStyle = "rgba(255, 255, 255, 0.035)";
      for (let y = 0; y < 768; y += 4) {
        ctx.fillRect(0, y, 1024, 1.8);
      }

      // 3. Monospace Code Diff Text
      ctx.font = "bold 52px 'Courier New', Courier, monospace";

      // Line 1: Deletion Line (Strikethrough Amber)
      ctx.fillStyle = "#E5A93C";
      ctx.fillText("-   const bug = true;", 120, 290);

      // Amber Strikethrough Line
      ctx.strokeStyle = "#E5A93C";
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.moveTo(225, 274);
      ctx.lineTo(820, 274);
      ctx.stroke();

      // Line 2: Addition Line (Soft Teal)
      ctx.fillStyle = "#5EEAD4";
      ctx.fillText("+   const bug = false;", 120, 410);

      // Blinking Terminal Block Cursor
      if (showCursor) {
        ctx.fillStyle = "#5EEAD4";
        ctx.fillRect(845, 360, 26, 52);
      }

      // Bottom Right: [CLICK TO PATCH] Label
      ctx.font = "bold 30px 'Courier New', Courier, monospace";
      ctx.fillStyle = "rgba(94, 234, 212, 0.85)";
      ctx.fillText("[CLICK TO PATCH]", 660, 680);

      screenTexture.needsUpdate = true;

      renderer.render(scene, camera);
    };

    animate();

    // 9. Resize Handling
    const handleResize = () => {
      if (!containerRef.current) return;
      const w = containerRef.current.clientWidth;
      const h = containerRef.current.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("resize", handleResize);
      cancelAnimationFrame(animationFrameId);
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className={`relative w-full h-full flex items-center justify-center select-none pointer-events-auto ${className}`}
      style={{ minHeight: "460px" }}
    />
  );
}
