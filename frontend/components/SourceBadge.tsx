// Lineage badge: AI-extracted / SME-confirmed / Verified / Low confidence.

import { ShieldCheck, Sparkles, TriangleAlert, UserCheck, type LucideIcon } from "lucide-react";

const SOURCES: Record<string, { text: string; Icon: LucideIcon; className: string }> = {
  ai_extracted: { text: "AI-extracted", Icon: Sparkles, className: "badge badge-ai" },
  sme_confirmed: { text: "SME-confirmed", Icon: UserCheck, className: "badge badge-confirmed" },
  verified: { text: "Verified", Icon: ShieldCheck, className: "badge badge-verified" },
  low_confidence: { text: "Low confidence", Icon: TriangleAlert, className: "badge badge-review" },
};

export function SourceBadge({ source }: { source: string | null | undefined }) {
  if (!source || !SOURCES[source]) return null;
  const s = SOURCES[source];
  return (
    <span className={s.className}>
      <s.Icon size={14} strokeWidth={1.5} aria-hidden="true" />
      {s.text}
    </span>
  );
}
