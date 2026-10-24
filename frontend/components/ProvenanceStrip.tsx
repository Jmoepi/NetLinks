import { SourceBadge } from "./SourceBadge";
import type { SourceType } from "@/lib/types";

// Compact provenance chain for an AI-derived answer: AI-extracted -> SME-confirmed -> Verified.

interface ProvenanceStripProps {
  sources: SourceType[];
}

export function ProvenanceStrip({ sources }: ProvenanceStripProps) {
  const unique = Array.from(new Set(sources.filter((s): s is SourceType => Boolean(s))));
  if (unique.length === 0) return null;
  return (
    <div className="provenance-strip">
      {unique.map((source) => (
        <SourceBadge key={source} source={source} />
      ))}
    </div>
  );
}
