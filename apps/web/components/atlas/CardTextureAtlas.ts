import * as THREE from "three";
import type { AtlasNode } from "./types";

export interface CardStyle {
  border: string;
  badgeBg: string;
  badgeText: string;
  badgeLabel: string;
}

export const LANGUAGE_STYLES: Record<string, { label: string; bg: string; text: string }> = {
  ts: { label: "TS", bg: "#3178C6", text: "#FFFFFF" },
  mts: { label: "TS", bg: "#3178C6", text: "#FFFFFF" },
  cts: { label: "TS", bg: "#3178C6", text: "#FFFFFF" },
  tsx: { label: "TSX", bg: "#3178C6", text: "#FFFFFF" },
  js: { label: "JS", bg: "#E8C547", text: "#111111" },
  mjs: { label: "JS", bg: "#E8C547", text: "#111111" },
  cjs: { label: "JS", bg: "#E8C547", text: "#111111" },
  jsx: { label: "JSX", bg: "#E8C547", text: "#111111" },
  py: { label: "PY", bg: "#4B8BBE", text: "#FFFFFF" },
  go: { label: "GO", bg: "#00ADD8", text: "#FFFFFF" },
  rs: { label: "RS", bg: "#DEA584", text: "#111111" },
  java: { label: "JAVA", bg: "#B07219", text: "#FFFFFF" },
  c: { label: "C", bg: "#555555", text: "#FFFFFF" },
  h: { label: "H", bg: "#555555", text: "#FFFFFF" },
  cpp: { label: "C++", bg: "#F34B7D", text: "#FFFFFF" },
  cc: { label: "C++", bg: "#F34B7D", text: "#FFFFFF" },
  cxx: { label: "C++", bg: "#F34B7D", text: "#FFFFFF" },
  hpp: { label: "H++", bg: "#F34B7D", text: "#FFFFFF" },
  rb: { label: "RB", bg: "#CC342D", text: "#FFFFFF" },
  php: { label: "PHP", bg: "#4F5D95", text: "#FFFFFF" },
  cs: { label: "C#", bg: "#178600", text: "#FFFFFF" },
  sh: { label: "SH", bg: "#89E051", text: "#111111" },
  bash: { label: "SH", bg: "#89E051", text: "#111111" },
  sql: { label: "SQL", bg: "#E38C00", text: "#FFFFFF" },
  html: { label: "HTML", bg: "#E34C26", text: "#FFFFFF" },
  css: { label: "#", bg: "#6B4FBB", text: "#FFFFFF" },
  scss: { label: "#", bg: "#6B4FBB", text: "#FFFFFF" },
  json: { label: "{}", bg: "#3F3F46", text: "#A1A1AA" },
  md: { label: "MD", bg: "#3F3F46", text: "#A1A1AA" },
  mdx: { label: "MD", bg: "#3F3F46", text: "#A1A1AA" },
  yml: { label: "YML", bg: "#3F3F46", text: "#A1A1AA" },
  yaml: { label: "YML", bg: "#3F3F46", text: "#A1A1AA" },
  toml: { label: "TOML", bg: "#3F3F46", text: "#A1A1AA" },
};

export function getLanguageStyle(ext: string, isBinary: boolean): { label: string; bg: string; text: string } {
  const cleanExt = ext.replace(/^\./, "").toLowerCase();
  if (isBinary) {
    return {
      label: cleanExt.slice(0, 4).toUpperCase() || "BIN",
      bg: "#3F3F46",
      text: "#A1A1AA",
    };
  }
  return (
    LANGUAGE_STYLES[cleanExt] || {
      label: cleanExt.slice(0, 3).toUpperCase() || "TXT",
      bg: "#3F3F46",
      text: "#A1A1AA",
    }
  );
}

const TEX_WIDTH = 512;
const TEX_HEIGHT = 320;

function formatBytes(bytes: number): string {
  if (!bytes || bytes <= 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export class CardTextureAtlas {
  /**
   * Bakes a crisp 512x320 canvas texture for a specific file node
   * conforming strictly to DESIGN.md and industrial cybernetic aesthetics.
   */
  static createCardTexture(
    node: AtlasNode,
    lastEditedText?: string,
    isBroken: boolean = false,
    isSelected: boolean = false
  ): THREE.CanvasTexture {
    const canvas = document.createElement("canvas");
    canvas.width = TEX_WIDTH;
    canvas.height = TEX_HEIGHT;
    const ctx = canvas.getContext("2d")!;

    // 1. Background — dark polycarbonate surface (#0d1117) with subtle inner bevel
    ctx.fillStyle = "#0d1117";
    ctx.fillRect(0, 0, TEX_WIDTH, TEX_HEIGHT);

    // Subtle ambient gradient sheen
    const bgGrad = ctx.createLinearGradient(0, 0, 0, TEX_HEIGHT);
    bgGrad.addColorStop(0, "rgba(255, 255, 255, 0.04)");
    bgGrad.addColorStop(1, "rgba(0, 0, 0, 0.2)");
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, TEX_WIDTH, TEX_HEIGHT);

    // 2. Outer Perimeter Border
    // Priority: broken (#E11D48) > selected (#5EEAD4) > default (#1E2430)
    let borderColor = "rgba(255, 255, 255, 0.12)";
    let borderWidth = 2.5;
    if (isBroken) {
      borderColor = "#F43F5E";
      borderWidth = 4;
    } else if (isSelected) {
      borderColor = "#FFFFFF";
      borderWidth = 3.5;
    }

    ctx.strokeStyle = borderColor;
    ctx.lineWidth = borderWidth;
    const r = 14;
    ctx.beginPath();
    ctx.roundRect(
      borderWidth / 2,
      borderWidth / 2,
      TEX_WIDTH - borderWidth,
      TEX_HEIGHT - borderWidth,
      r
    );
    ctx.stroke();

    const padding = 34;
    const langStyle = getLanguageStyle(node.ext, node.is_binary);

    // 3. Row 1: Language badge (top-left) & last-edited / status (top-right)
    const badgeW = 56;
    const badgeH = 34;
    const badgeX = padding;
    const badgeY = padding;

    ctx.fillStyle = langStyle.bg;
    ctx.beginPath();
    ctx.roundRect(badgeX, badgeY, badgeW, badgeH, 6);
    ctx.fill();

    ctx.fillStyle = langStyle.text;
    ctx.font = "bold 18px monospace, ui-monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(langStyle.label, badgeX + badgeW / 2, badgeY + badgeH / 2 + 1);

    // Top-right: Broken indicator pill OR last-edited commit metadata
    if (isBroken) {
      ctx.textAlign = "right";
      ctx.textBaseline = "middle";
      ctx.fillStyle = "#F43F5E";
      ctx.font = "bold 17px monospace, ui-monospace";
      ctx.fillText("● BROKEN", TEX_WIDTH - padding, badgeY + badgeH / 2);
    } else if (lastEditedText) {
      ctx.textAlign = "right";
      ctx.textBaseline = "middle";
      ctx.fillStyle = "#7E7E8A";
      ctx.font = "18px monospace, ui-monospace";
      ctx.fillText(lastEditedText, TEX_WIDTH - padding, badgeY + badgeH / 2);
    } else {
      // Skeleton bar at 8% opacity
      ctx.fillStyle = "rgba(255, 255, 255, 0.08)";
      ctx.beginPath();
      ctx.roundRect(TEX_WIDTH - padding - 85, badgeY + 8, 85, 16, 4);
      ctx.fill();
    }

    if (node.is_binary) {
      // Binary card layout: Centered glyph + No preview notice
      ctx.textAlign = "center";
      ctx.fillStyle = "#52525B";
      ctx.font = "28px monospace, ui-monospace";
      ctx.fillText("▧", TEX_WIDTH / 2, TEX_HEIGHT / 2 - 12);

      ctx.fillStyle = "#A1A1AA";
      ctx.font = "600 22px monospace, ui-monospace";
      ctx.fillText(node.name, TEX_WIDTH / 2, TEX_HEIGHT / 2 + 24);

      ctx.fillStyle = "#7E7E8A";
      ctx.font = "16px monospace, ui-monospace";
      ctx.fillText("Binary file · No preview", TEX_WIDTH / 2, TEX_HEIGHT / 2 + 56);
    } else {
      // Code / text card layout
      // Row 2: Filename
      ctx.textAlign = "left";
      ctx.fillStyle = "#FFFFFF";
      ctx.font = "600 28px monospace, ui-monospace";
      let nameText = node.name;
      if (ctx.measureText(nameText).width > TEX_WIDTH - padding * 2) {
        while (
          ctx.measureText(nameText + "…").width > TEX_WIDTH - padding * 2 &&
          nameText.length > 3
        ) {
          nameText = nameText.slice(0, -1);
        }
        nameText += "…";
      }
      ctx.fillText(nameText, padding, 142);

      // Row 3: Folder path
      ctx.fillStyle = "#A1A1AA";
      ctx.font = "18px monospace, ui-monospace";
      let dirText = node.dir ? `${node.dir}/` : "/";
      if (ctx.measureText(dirText).width > TEX_WIDTH - padding * 2) {
        while (
          ctx.measureText("…/" + dirText).width > TEX_WIDTH - padding * 2 &&
          dirText.length > 5
        ) {
          dirText = dirText.slice(1);
        }
        dirText = "…/" + dirText;
      }
      ctx.fillText(dirText, padding, 185);

      // Row 4: Bottom Telemetry
      // Left: File size
      ctx.textAlign = "left";
      ctx.fillStyle = "#7E7E8A";
      ctx.font = "17px monospace, ui-monospace";
      ctx.fillText(formatBytes(node.size_bytes), padding, TEX_HEIGHT - padding);

      // Right: Unresolved import badge
      if (node.unresolved_import_count > 0) {
        ctx.textAlign = "right";
        ctx.fillStyle = "#F59E0B";
        ctx.font = "bold 17px monospace, ui-monospace";
        ctx.fillText(
          `⚠ ${node.unresolved_import_count} unresolved`,
          TEX_WIDTH - padding,
          TEX_HEIGHT - padding
        );
      }
    }

    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.minFilter = THREE.LinearFilter;
    texture.magFilter = THREE.LinearFilter;
    return texture;
  }
}
