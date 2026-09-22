import * as THREE from "three";
import type { AtlasNode } from "./types";
import { CARD_WIDTH, CARD_HEIGHT } from "./LayeredLayout";

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
  json: { label: "{}", bg: "#3F3F46", text: "#A1A1AA" },
  md: { label: "MD", bg: "#3F3F46", text: "#A1A1AA" },
  mdx: { label: "MD", bg: "#3F3F46", text: "#A1A1AA" },
  css: { label: "#", bg: "#6B4FBB", text: "#FFFFFF" },
  scss: { label: "#", bg: "#6B4FBB", text: "#FFFFFF" },
  yml: { label: "YML", bg: "#3F3F46", text: "#A1A1AA" },
  yaml: { label: "YML", bg: "#3F3F46", text: "#A1A1AA" },
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

export class CardTextureAtlas {
  /**
   * Bakes a crisp 512x320 canvas texture for a specific file node
   * conforming strictly to Section 7.4a.
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

    // 1. Background — glass fill rgba(255,255,255,0.03) over pure black
    ctx.fillStyle = "#020203";
    ctx.fillRect(0, 0, TEX_WIDTH, TEX_HEIGHT);

    ctx.fillStyle = "rgba(255, 255, 255, 0.03)";
    ctx.fillRect(0, 0, TEX_WIDTH, TEX_HEIGHT);

    // 2. Border
    // Priority: broken (#E11D48) > selected (#5EEAD4) > default
    let borderColor = "rgba(255, 255, 255, 0.14)";
    let borderWidth = 2;
    if (isBroken) {
      borderColor = "#E11D48";
      borderWidth = 4;
    } else if (isSelected) {
      borderColor = "#5EEAD4";
      borderWidth = 3;
    }

    ctx.strokeStyle = borderColor;
    ctx.lineWidth = borderWidth;
    const r = 12; // 6px relative to world size
    ctx.beginPath();
    ctx.roundRect(borderWidth / 2, borderWidth / 2, TEX_WIDTH - borderWidth, TEX_HEIGHT - borderWidth, r);
    ctx.stroke();

    const padding = 36;
    const langStyle = getLanguageStyle(node.ext, node.is_binary);

    // 3. Row 1: Language badge (top-left) & last-edited (top-right)
    const badgeW = 54;
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

    // Last-edited (top-right)
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    if (lastEditedText) {
      ctx.fillStyle = "#71717A";
      ctx.font = "18px monospace, ui-monospace";
      ctx.fillText(lastEditedText, TEX_WIDTH - padding, badgeY + badgeH / 2);
    } else {
      // Skeleton bar at 8% opacity
      ctx.fillStyle = "rgba(255, 255, 255, 0.08)";
      ctx.beginPath();
      ctx.roundRect(TEX_WIDTH - padding - 90, badgeY + 8, 90, 16, 4);
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

      ctx.fillStyle = "#71717A";
      ctx.font = "16px monospace, ui-monospace";
      ctx.fillText("No preview available", TEX_WIDTH / 2, TEX_HEIGHT / 2 + 56);
    } else {
      // Code / text card layout
      // Row 2: Filename
      ctx.textAlign = "left";
      ctx.fillStyle = isBroken ? "#FFFFFF" : "#FFFFFF";
      ctx.font = "600 28px monospace, ui-monospace";
      let nameText = node.name;
      if (ctx.measureText(nameText).width > TEX_WIDTH - padding * 2) {
        while (ctx.measureText(nameText + "…").width > TEX_WIDTH - padding * 2 && nameText.length > 3) {
          nameText = nameText.slice(0, -1);
        }
        nameText += "…";
      }
      ctx.fillText(nameText, padding, 140);

      // Row 3: Folder path (truncated left with …/ if wide)
      ctx.fillStyle = "#A1A1AA";
      ctx.font = "18px monospace, ui-monospace";
      let dirText = node.dir ? `${node.dir}/` : "/";
      if (ctx.measureText(dirText).width > TEX_WIDTH - padding * 2) {
        while (ctx.measureText("…/" + dirText).width > TEX_WIDTH - padding * 2 && dirText.length > 5) {
          dirText = dirText.slice(1);
        }
        dirText = "…/" + dirText;
      }
      ctx.fillText(dirText, padding, 185);

      // Row 4: Unresolved import badge (bottom-right) if unresolved_import_count > 0
      if (node.unresolved_import_count > 0) {
        ctx.textAlign = "right";
        ctx.fillStyle = "#71717A";
        ctx.font = "17px monospace, ui-monospace";
        ctx.fillText(`⚠ ${node.unresolved_import_count}`, TEX_WIDTH - padding, TEX_HEIGHT - padding);
      }
    }

    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.minFilter = THREE.LinearFilter;
    texture.magFilter = THREE.LinearFilter;
    return texture;
  }
}
