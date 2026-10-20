// Lineage badge: AI-extracted / SME-confirmed / Verified / Low confidence.

const SOURCES: Record<string, { text: string; icon: string; className: string }> = {
  ai_extracted: { text: "AI-extracted", icon: "✦", className: "badge badge-ai" },
  sme_confirmed: { text: "SME-confirmed", icon: "✓", className: "badge badge-confirmed" },
  verified: { text: "Verified", icon: "★", className: "badge badge-verified" },
  low_confidence: { text: "Low confidence", icon: "!", className: "badge badge-review" },
};

export function SourceBadge({ source }: { source: string | null | undefined }) {
  if (!source || !SOURCES[source]) return null;
  const s = SOURCES[source];
  return (
    <span className={s.className}>
      <span aria-hidden="true" className="badge-icon">
        {s.icon}
      </span>
      {s.text}
    </span>
  );
}
