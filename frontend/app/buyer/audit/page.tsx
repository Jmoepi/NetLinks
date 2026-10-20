"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { Notice } from "@/components/Notice";
import { RoleGate } from "@/components/RoleGate";
import { formatDateTime } from "@/lib/format";
import { useLoad } from "@/lib/useLoad";
import type { AuditEntry } from "@/lib/types";

const ACTION_LABELS: Record<string, string> = {
  extraction: "AI extraction",
  sme_correction: "SME correction",
  sme_confirmation: "SME confirmation",
  consent: "Consent",
  requirement_edit: "Requirement edit",
  rfq_structured: "RFQ structured by AI",
  match_run: "Match run",
  info_request: "Information request",
  info_request_responded: "Request responded",
  shortlist_decision: "Shortlist decision",
  override: "Override",
  ai_mode_change: "AI mode change",
  demo_reset: "Demo reset",
};

/** One-line plain-language summary of the audit details; the full JSON is available below it. */
function summarize(entry: AuditEntry): string {
  const d = entry.details as Record<string, unknown>;
  switch (entry.action) {
    case "extraction":
      return `${d.filename} (${d.field_count} fields) by ${d.provider} / ${d.model_id}${d.cache_hit ? ", cached" : ""}`;
    case "sme_correction": {
      const old = ((d.old as { value: unknown }[]) || []).map((o) => JSON.stringify(o.value)).join(" / ");
      return `${d.field_key}: ${old || "(none)"} -> ${JSON.stringify(d.new)}${d.note ? ` (note: ${d.note})` : ""}`;
    }
    case "sme_confirmation":
      return `${d.field_key} confirmed as ${JSON.stringify(d.value)} (was ${String(d.previous_source_type).replace("_", "-")})`;
    case "consent":
      return d.granted ? "Profile shared with buyers" : "Sharing declined";
    case "requirement_edit": {
      const vsProposal = d.changes_vs_proposal as { summary: string }[] | null;
      const vsPrev = (d.changes_vs_previous as { summary: string }[]) || [];
      const list = vsProposal ?? vsPrev;
      return list.length ? `${list.map((c) => c.summary).join("; ")}${vsProposal ? " (vs AI proposal)" : ""}` : "No changes";
    }
    case "match_run": {
      const c = (d.counts || {}) as Record<string, number>;
      return `Eligible ${c.eligible ?? 0}, Needs Review ${c.needs_review ?? 0}, Not Eligible ${c.not_eligible ?? 0}`;
    }
    case "info_request":
      return `${d.kind} request to ${d.sme_slug ?? "SME"}: ${d.message ?? ""}`;
    case "info_request_responded":
      return `${d.kind} request answered by upload`;
    case "shortlist_decision":
      return `Shortlisted ${d.sme_slug ?? ""} at position ${d.position} (engine rank ${d.engine_rank ?? "none"})`;
    case "override":
      return `Order ${(d.from as string[] | undefined)?.join(", ") ?? ""} -> ${(d.to as string[] | undefined)?.join(", ") ?? ""}`;
    case "ai_mode_change":
      return `${d.from} -> ${d.to}`;
    default:
      return "";
  }
}

function formatDetail(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function AuditTable() {
  const search = useSearchParams();
  const opp = search.get("opportunity_id");
  const path = opp && /^\d+$/.test(opp) ? `/api/audit?opportunity_id=${opp}` : "/api/audit";
  const { data, error, loading, reload } = useLoad<{ entries: AuditEntry[] }>(path);

  if (!data) return loading ? <p>Loading audit log…</p> : <Notice kind="error">{error}</Notice>;

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Audit log</h1>
          <p className="muted">
            Append-only. Every entry is timestamped and attributed to a role. {data.entries.length} entries, oldest first.
          </p>
        </div>
        <button type="button" className="secondary" onClick={() => void reload()}>
          Refresh
        </button>
      </div>
      <div className="table-wrap">
        <table>
          <caption className="sr-only">Audit log entries</caption>
          <thead>
            <tr>
              <th scope="col">Time</th>
              <th scope="col">Role</th>
              <th scope="col">Actor</th>
              <th scope="col">Action</th>
              <th scope="col">Entity</th>
              <th scope="col">Details</th>
              <th scope="col">Reason</th>
            </tr>
          </thead>
          <tbody>
            {data.entries.map((e) => (
              <tr key={e.id}>
                <td>{formatDateTime(e.at)}</td>
                <td>{e.actor_role}</td>
                <td>{e.actor_label}</td>
                <td>{ACTION_LABELS[e.action] || e.action}</td>
                <td>
                  {e.entity_type} {e.entity_id ?? ""}
                </td>
                <td>
                  {summarize(e)}
                  <details>
                    <summary>
                      Full details<span className="sr-only"> for entry {e.id}</span>
                    </summary>
                    <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.8rem" }}>{formatDetail(e.details)}</pre>
                  </details>
                </td>
                <td>{e.reason || ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function AuditPage() {
  return (
    <RoleGate roles={["buyer", "admin"]}>
      <Suspense fallback={<p>Loading audit log…</p>}>
        <AuditTable />
      </Suspense>
    </RoleGate>
  );
}
