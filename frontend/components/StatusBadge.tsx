// Status shown as text + icon + colour (never colour alone).

const STATUS: Record<string, { text: string; icon: string; className: string }> = {
  eligible: { text: "Eligible", icon: "✓", className: "badge badge-eligible" },
  needs_review: { text: "Needs Review", icon: "!", className: "badge badge-review" },
  not_eligible: { text: "Not Eligible", icon: "✕", className: "badge badge-fail" },
  awaiting_sme: { text: "Awaiting SME", icon: "⏳", className: "badge badge-awaiting" },
  pass: { text: "Pass", icon: "✓", className: "badge badge-eligible" },
  fail: { text: "Fail", icon: "✕", className: "badge badge-fail" },
  not_assessed: { text: "Not yet assessed", icon: "–", className: "badge badge-neutral" },
};

export function StatusBadge({ status, suffix = "" }: { status: string | null | undefined; suffix?: string }) {
  const s = STATUS[status || "not_assessed"] || STATUS.not_assessed;
  return (
    <span className={s.className}>
      <span aria-hidden="true" className="badge-icon">
        {s.icon}
      </span>
      {s.text}
      {suffix}
    </span>
  );
}
