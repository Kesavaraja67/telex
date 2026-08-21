interface BadgeProps {
  status: "open" | "merged" | "closed" | "pending" | "patched" | "failed";
  className?: string;
}

const styleMap: Record<string, string> = {
  open:    "border-white/30 text-white bg-white/[0.06]",
  pending: "border-white/30 text-white bg-white/[0.06]",
  merged:  "border-white/50 text-white bg-white/[0.12]",
  patched: "border-white/50 text-white bg-white/[0.12]",
  closed:  "border-white/10 text-[#888888] bg-white/[0.02]",
  failed:  "border-white/20 text-[#888888] bg-white/[0.04]",
};

const labelMap: Record<string, string> = {
  open:    "OPEN",
  pending: "PENDING",
  merged:  "MERGED",
  patched: "PATCHED",
  closed:  "CLOSED",
  failed:  "FAILED",
};

export default function Badge({ status, className = "" }: BadgeProps) {
  return (
    <span
      className={[
        "font-mono text-[9px] sm:text-[10px] font-semibold tracking-widest uppercase px-2.5 py-0.5 rounded-full border backdrop-blur-md inline-flex items-center gap-1.5",
        styleMap[status] ?? "border-white/20 text-white",
        className,
      ].join(" ")}
    >
      <span
        className="w-1 h-1 rounded-full inline-block"
        style={{
          backgroundColor:
            status === "merged" || status === "patched" || status === "open" || status === "pending"
              ? "#FFFFFF"
              : "#888888",
        }}
      />
      {labelMap[status] ?? status.toUpperCase()}
    </span>
  );
}
