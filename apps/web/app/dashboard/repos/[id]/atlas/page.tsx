"use client";

import { use } from "react";
import dynamic from "next/dynamic";

const AtlasView = dynamic(() => import("@/components/atlas/AtlasView"), {
  ssr: false,
  loading: () => (
    <div style={{ position: "fixed", inset: 0, background: "#000" }} />
  ),
});

export default function AtlasPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return <AtlasView repoId={id} />;
}
