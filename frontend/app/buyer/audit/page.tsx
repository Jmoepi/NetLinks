"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useId } from "react";
import { Eyebrow } from "@/components/Eyebrow";
import { Notice } from "@/components/Notice";
import { Pagination } from "@/components/Pagination";
import { RoleGate } from "@/components/RoleGate";
import { formatDateTime } from "@/lib/format";
import { usePageParam } from "@/lib/pagination";
import { useLoad } from "@/lib/useLoad";
import type { AuditEntry, AuditPage } from "@/lib/types";

const PAGE_SIZE = 20;

/** Event types offered by the filter; keys match backend app.audit.ACTIONS. */
const ACTION_LABELS: Record<string, string> = {
  extraction: "AI extraction",
  sme_correction: "SME correction",
  sme_confirmation: "SME confirmation",
  sme_profile_entry: "SME profile entry",
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

/** Role filter (?role=) mapped to the API's actor_role values. */
const ROLE_LABELS: Record<string, string> = {
  sme: "SME",
  buyer: "Buyer",
  admin: "YES Admin",
  system: "System",
};

/** One-line plain-language summary of the audit details; the full JSON is available below it. */
function summarize(entry: AuditEntry): string {
  const d = entry.details as Record<string, unknown>;
  switch (entry.action) {
    case "extraction":
      return `${d.filename} (${d.field_count} field${d.field_count === 1 ? "" : "s"}) by ${d.provider} / ${d.model_id}${d.cache_hit ? ", cached" : ""}`;
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
  const pathname = usePathname();
  const router = useRouter();
  const { page, setPage, hrefFor } = usePageParam("page");
  const actionId = useId();
  const roleId = useId();

  const opp = search.get("opportunity_id");
  const rawAction = search.get("action");
  const action = rawAction && Object.prototype.hasOwnProperty.call(ACTION_LABELS, rawAction) ? rawAction : "";
  const rawRole = search.get("role");
  const role = rawRole && Object.prototype.hasOwnProperty.call(ROLE_LABELS, rawRole) ? rawRole : "";

  let path = `/api/audit?page=${page}&page_size=${PAGE_SIZE}`;
  if (opp && /^\d+$/.test(opp)) path += `&opportunity_id=${opp}`;
  if (action) path += `&action=${action}`;
  if (role) path += `&actor_role=${role}`;
  const { data, error, loading, reload } = useLoad<AuditPage>(path);

  // A page past the end (e.g. after a reset) jumps to the last page instead of showing an empty list.
  useEffect(() => {
    if (data && data.entries.length === 0 && data.total > 0 && data.page > 1) {
      router.replace(hrefFor(Math.ceil(data.total / data.page_size)), { scroll: false });
    }
  }, [data, hrefFor, router]);

  /** Change a filter in the URL; any filter change returns to page 1. */
  function setFilter(key: "action" | "role", value: string) {
    const params = new URLSearchParams(search.toString());
    if (value) params.set(key, value);
    else params.delete(key);
    params.delete("page");
    const qs = params.toString();
    router.push(`${pathname}${qs ? `?${qs}` : ""}`, { scroll: false });
  }

  if (!data) return loading ? <p>Loading audit log…</p> : <Notice kind="error">{error}</Notice>;

  return (
    <div className="timeline">
      <div className="timeline-aside">
        <div>
          <Eyebrow label="Audit" />
          <h1>Audit log</h1>
          <p className="muted">
            Append-only. Every entry is timestamped and attributed to a role. {data.total} entries, newest first.
          </p>
          <div className="audit-filters">
            <div className="field">
              <label htmlFor={actionId}>Event type</label>
              <select id={actionId} value={action} onChange={(e) => setFilter("action", e.target.value)}>
                <option value="">All</option>
                {Object.entries(ACTION_LABELS).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor={roleId}>Role</label>
              <select id={roleId} value={role} onChange={(e) => setFilter("role", e.target.value)}>
                <option value="">All</option>
                {Object.entries(ROLE_LABELS).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="button-row">
            <button type="button" className="secondary" onClick={() => void reload()}>
              Refresh
            </button>
          </div>
        </div>
      </div>
      <div>
      {data.total === 0 ? <p className="muted">No entries match these filters.</p> : null}
      <ol className="timeline-list" aria-label="Audit log entries">
        {data.entries.map((e) => (
          <li key={e.id}>
            <time dateTime={e.at}>{formatDateTime(e.at)}</time>
            <div>
              <h3>{ACTION_LABELS[e.action] || e.action}</h3>
              <div className="timeline-who">
                <span className="pill">
                  <span className="sr-only">Role: </span>
                  {e.actor_role}
                </span>
              </div>
              <dl className="audit-meta">
                <dt>Actor</dt>
                <dd>{e.actor_label}</dd>
                <dt>Entity</dt>
                <dd className="mono">
                  {e.entity_type} {e.entity_id ?? ""}
                </dd>
                <dt>Details</dt>
                <dd>
                  {summarize(e)}
                  <details>
                    <summary>
                      Full details<span className="sr-only"> for entry {e.id}</span>
                    </summary>
                    <pre>{formatDetail(e.details)}</pre>
                  </details>
                </dd>
                {e.reason ? (
                  <>
                    <dt>Reason</dt>
                    <dd>{e.reason}</dd>
                  </>
                ) : null}
              </dl>
            </div>
          </li>
        ))}
      </ol>
      <Pagination
        label="Audit log"
        page={data.page}
        pageSize={data.page_size}
        total={data.total}
        onPageChange={setPage}
      />
      </div>
    </div>
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
