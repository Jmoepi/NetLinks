// Display helpers shared by the screens.

const PROVINCES: Record<string, string> = {
  GP: "Gauteng",
  WC: "Western Cape",
  KZN: "KwaZulu-Natal",
  EC: "Eastern Cape",
  FS: "Free State",
  LP: "Limpopo",
  MP: "Mpumalanga",
  NW: "North West",
  NC: "Northern Cape",
};

export const DOC_TYPE_LABELS: Record<string, string> = {
  capability_statement: "Capability statement",
  certification_summary: "Certification summary",
  infosec_popia_policy: "Information security & POPIA policy",
  pi_schedule: "PI insurance schedule",
  tax_compliance_letter: "Tax compliance letter",
  other: "Other document",
};

export const INTEGER_FIELDS = new Set([
  "technician_count",
  "years_trading",
  "pi_cover_amount",
  "black_ownership_pct",
  "bbbee_level",
]);

const MONEY_FIELDS = new Set(["pi_cover_amount", "min_amount"]);

export function rand(amount: number): string {
  return `R${Math.round(amount).toLocaleString("en-US")}`;
}

export function provinceName(code: string): string {
  return PROVINCES[code] ? `${PROVINCES[code]} (${code})` : code;
}

export function docTypeLabel(docType: string | null | undefined): string {
  if (!docType) return "Unclassified document";
  return DOC_TYPE_LABELS[docType] || docType;
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-ZA", { dateStyle: "medium", timeStyle: "short" });
}

/** Human-readable profile value, e.g. lists of certifications or "R2,000,000". */
export function formatValue(fieldKey: string | null, value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not provided";
  if (fieldKey && MONEY_FIELDS.has(fieldKey) && typeof value === "number") return rand(value);
  if (fieldKey === "black_ownership_pct" && typeof value === "number") return `${value}%`;
  if (fieldKey === "bbbee_level" && typeof value === "number") return `Level ${value}`;
  if (fieldKey === "service_regions" && Array.isArray(value)) return value.map((v) => provinceName(String(v))).join(", ");
  if (fieldKey === "province" && typeof value === "string") return provinceName(value);
  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (item && typeof item === "object") {
          const o = item as Record<string, unknown>;
          if ("cert_name" in o) {
            return `${o.cert_name} (${o.holder ?? "unknown holder"}, expires ${o.expiry_date ?? "unreadable date"})`;
          }
          if ("user_count" in o) return `${o.name} (${o.user_count} users)`;
          return JSON.stringify(o);
        }
        return String(item).replace(/_/g, " ");
      })
      .join("; ");
  }
  if (typeof value === "object") {
    const o = value as Record<string, unknown>;
    if ("start" in o && "end" in o) return `${o.start} to ${o.end}`;
    return JSON.stringify(o);
  }
  return String(value);
}

/** Link to the document viewer with the source span highlighted. */
export function sourceHref(ref: {
  document_id: number | null;
  page?: number | null;
  span_start?: number | null;
  span_end?: number | null;
}): string | null {
  if (!ref.document_id) return null;
  const params = new URLSearchParams();
  if (ref.page) params.set("page", String(ref.page));
  if (ref.span_start !== null && ref.span_start !== undefined) params.set("start", String(ref.span_start));
  if (ref.span_end !== null && ref.span_end !== undefined) params.set("end", String(ref.span_end));
  const qs = params.toString();
  return `/documents/${ref.document_id}${qs ? `?${qs}` : ""}`;
}

export function confidenceText(confidence: number | null | undefined): string {
  if (confidence === null || confidence === undefined) return "-";
  return `${Math.round(confidence * 100)}%`;
}
