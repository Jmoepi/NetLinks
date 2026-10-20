// Status shown as text + icon + colour (never colour alone).

import { Check, CircleCheck, CircleX, Hourglass, Minus, TriangleAlert, X, type LucideIcon } from "lucide-react";

const STATUS: Record<string, { text: string; Icon: LucideIcon; className: string }> = {
  eligible: { text: "Eligible", Icon: CircleCheck, className: "badge badge-eligible" },
  needs_review: { text: "Needs Review", Icon: TriangleAlert, className: "badge badge-review" },
  not_eligible: { text: "Not Eligible", Icon: CircleX, className: "badge badge-fail" },
  awaiting_sme: { text: "Awaiting SME", Icon: Hourglass, className: "badge badge-awaiting" },
  pass: { text: "Pass", Icon: Check, className: "badge badge-eligible" },
  fail: { text: "Fail", Icon: X, className: "badge badge-fail" },
  not_assessed: { text: "Not yet assessed", Icon: Minus, className: "badge badge-neutral" },
};

export function StatusBadge({ status, suffix = "" }: { status: string | null | undefined; suffix?: string }) {
  const s = STATUS[status || "not_assessed"] || STATUS.not_assessed;
  return (
    <span className={s.className}>
      <s.Icon size={14} strokeWidth={1.5} aria-hidden="true" />
      {s.text}
      {suffix}
    </span>
  );
}
