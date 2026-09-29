interface BadgeProps {
  status: "open" | "merged" | "closed" | "pending" | "patched" | "failed" | "verified" | "generated";
  className?: string;
}

const ledStateMap: Record<string, "ok" | "warn" | "fault" | "busy" | "off"> = {
  merged:    "ok",
  patched:   "ok",
  verified:  "ok",
  pending:   "busy",
  generated: "busy",
  open:      "warn",
  failed:    "fault",
  closed:    "off",
};

const labelMap: Record<string, string> = {
  open:      "OPEN",
  pending:   "PENDING",
  merged:    "MERGED",
  patched:   "PATCHED",
  verified:  "VERIFIED",
  generated: "GENERATED",
  closed:    "CLOSED",
  failed:    "FAILED",
};

export default function Badge({ status, className = "" }: BadgeProps) {
  const ledState = ledStateMap[status] ?? "off";

  return (
    <span
      className={[
        "badge-chip",
        className,
      ].join(" ")}
    >
      <span
        className="led"
        data-state={ledState}
        style={{ width: "7px", height: "7px" }}
        aria-hidden="true"
      />
      <span>{labelMap[status] ?? status.toUpperCase()}</span>
    </span>
  );
}

