import Link from "next/link";
import { docTypeLabel, formatValue, sourceHref } from "@/lib/format";
import type { Evidence } from "@/lib/types";
import { SourceBadge } from "./SourceBadge";

/** Evidence list: quote + source badge + "View source" link that highlights the span. */
export function EvidenceLinks({ evidence }: { evidence: Evidence[] }) {
  if (!evidence.length) return null;
  return (
    <ul className="evidence-list">
      {evidence.map((e, i) => {
        const href = sourceHref(e);
        const source = e.document_id ? `${docTypeLabel(e.doc_type)} (${e.source_label})` : e.source_label || "SME entry";
        return (
          <li key={`${e.candidate_id ?? "doc"}-${e.document_id ?? "x"}-${i}`}>
            {e.quote ? <q>{e.quote}</q> : e.field_key ? <span>{formatValue(e.field_key, e.value)}</span> : null}{" "}
            <span className="muted">from {source}</span> <SourceBadge source={e.source_type} />{" "}
            {href ? (
              <Link href={href}>
                View source<span className="sr-only"> in {e.source_label}</span>
              </Link>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
