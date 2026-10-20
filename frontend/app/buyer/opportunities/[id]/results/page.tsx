"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useId, useState, type FormEvent } from "react";
import { EvidenceLinks } from "@/components/EvidenceLinks";
import { Notice } from "@/components/Notice";
import { RoleGate } from "@/components/RoleGate";
import { SourceBadge } from "@/components/SourceBadge";
import { StatusBadge } from "@/components/StatusBadge";
import { api, errorMessage } from "@/lib/api";
import { formatDateTime, formatValue, sourceHref } from "@/lib/format";
import { useIdentity } from "@/lib/identity";
import { useLoad } from "@/lib/useLoad";
import type { Check, MatchResult, MatchStatus, RunPayload, ShortlistEntry } from "@/lib/types";

const GROUPS: { key: MatchStatus; title: string }[] = [
  { key: "eligible", title: "Eligible" },
  { key: "needs_review", title: "Needs Review" },
  { key: "not_eligible", title: "Not Eligible" },
];

function daysBetween(a: string, b: string): number {
  return Math.round((Date.parse(b) - Date.parse(a)) / 86_400_000);
}

/** Expiry date vs closing date, side by side (outdated evidence goes to review, never rejection). */
function DatePanel({ check }: { check: Check }) {
  const { expiry_date: expiry, closing_date: closing } = check.details;
  if (!expiry || !closing || !check.issues.includes("outdated")) return null;
  const days = daysBetween(expiry, closing);
  return (
    <div className="side-by-side" role="group" aria-label={`${check.label}: expiry date compared with closing date`}>
      <div>
        <span className="muted">Evidence expires</span>
        <div className="big">{expiry}</div>
      </div>
      <div>
        <span className="muted">Opportunity closing date</span>
        <div className="big">{closing}</div>
      </div>
      <div>
        <span className="muted">Gap</span>
        <div className="big">
          {days > 0 ? `${days} days before closing` : days === 0 ? "Expires on the closing date" : `${-days} days after`}
        </div>
      </div>
    </div>
  );
}

/** Conflicting values from different sources, side by side. */
function ConflictPanel({ check }: { check: Check }) {
  const conflicts = check.details.conflicts;
  if (!conflicts?.length) return null;
  return (
    <>
      {conflicts.map((c) => (
        <div key={c.field_key} role="group" aria-label={`${c.label}: conflicting sources`}>
          <strong>{c.label}: sources disagree</strong>
          <div className="side-by-side">
            {c.values.map((v, i) => {
              const ev = check.evidence.find((e) => e.field_key === c.field_key && e.document_id === v.document_id);
              const href = ev ? sourceHref(ev) : v.document_id ? `/documents/${v.document_id}` : null;
              return (
                <div key={i}>
                  <span className="muted">{v.source}</span>
                  <div className="big">{formatValue(c.field_key, v.value)}</div>
                  <SourceBadge source={v.source_type} />{" "}
                  {href ? (
                    <Link href={href}>
                      View source<span className="sr-only"> ({v.source})</span>
                    </Link>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </>
  );
}

function CheckItem({ check }: { check: Check }) {
  return (
    <li>
      <StatusBadge status={check.outcome} /> <strong>{check.label}</strong>
      <div>{check.reason}</div>
      <DatePanel check={check} />
      <ConflictPanel check={check} />
      {!check.details.conflicts?.length ? <EvidenceLinks evidence={check.evidence} /> : null}
    </li>
  );
}

function suggestedMessage(result: MatchResult, kind: "information" | "clarification"): string {
  const issues = result.checks.filter((c) => c.outcome !== "pass");
  if (kind === "information" && issues.some((c) => c.rule === "pi_insurance" && c.issues.includes("outdated"))) {
    return "Please upload your renewed professional indemnity schedule.";
  }
  const conflict = issues.flatMap((c) => c.details.conflicts || []).find((c) => c.field_key === "technician_count");
  if (kind === "clarification" && conflict) {
    const parts = conflict.values.map((v) => `${v.source} says ${formatValue(conflict.field_key, v.value)}`);
    return `Please clarify your technician count: ${parts.join(" and ")}.`;
  }
  return "";
}

function RequestForm({
  opportunityId,
  result,
  kind,
  onSent,
  onCancel,
}: {
  opportunityId: string;
  result: MatchResult;
  kind: "information" | "clarification";
  onSent: () => Promise<void>;
  onCancel: () => void;
}) {
  const id = useId();
  const [message, setMessage] = useState(() => suggestedMessage(result, kind));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { identity } = useIdentity();

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!message.trim()) {
      setError("Write a message to the SME.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/opportunities/${opportunityId}/info-requests`, {
        sme_slug: result.sme.slug,
        kind,
        message: message.trim(),
      });
      await onSent();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="panel" aria-label={`Request ${kind} from ${result.sme.name}`}>
      <div className="field">
        <label htmlFor={id}>
          {kind === "information" ? "Request information" : "Request clarification"}: message to {result.sme.name}
        </label>
        <textarea id={id} rows={3} maxLength={2000} value={message} onChange={(e) => setMessage(e.target.value)} />
        <span className="hint">Sent as {identity?.label}. Recorded in the audit log.</span>
      </div>
      <div className="button-row">
        <button type="submit" disabled={busy}>
          Send request
        </button>
        <button type="button" className="secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
      <Notice kind="error">{error}</Notice>
    </form>
  );
}

function ResultCard({
  opportunityId,
  result,
  shortlisted,
  onShortlist,
  onChanged,
}: {
  opportunityId: string;
  result: MatchResult;
  shortlisted: boolean;
  onShortlist: (slug: string) => Promise<void>;
  onChanged: () => Promise<void>;
}) {
  const [form, setForm] = useState<"information" | "clarification" | null>(null);
  const [busy, setBusy] = useState(false);
  const mandatory = result.checks.filter((c) => c.group === "mandatory");
  const consistency = result.checks.filter((c) => c.group !== "mandatory");
  const issues = result.checks.filter((c) => c.outcome !== "pass");
  const passCount = mandatory.filter((c) => c.outcome === "pass").length;
  const headingId = useId();

  return (
    <article className={`result-card status-${result.status}`} aria-labelledby={headingId}>
      <div className="result-head">
        {result.rank ? (
          <span className="rank" aria-label={`Rank ${result.rank}`}>
            #{result.rank}
          </span>
        ) : null}
        <h3 id={headingId}>{result.sme.name}</h3>
        <StatusBadge status={result.status} />
        {result.awaiting_sme ? <StatusBadge status="awaiting_sme" /> : null}
        {shortlisted ? (
          <span className="badge badge-confirmed">
            <span aria-hidden="true">★</span>Shortlisted
          </span>
        ) : null}
        <span className="score">
          {result.provisional ? "Provisional score" : "Fit score"} {result.score_total.toFixed(1)} / 100
        </span>
      </div>
      <p className="muted" style={{ margin: "0.25rem 0" }}>
        {result.sme.base_town} · {result.sme.size_band} business
        {result.provisional ? " · no rank until the review items are resolved" : ""}
      </p>

      {issues.length ? (
        <div>
          <h4 style={{ margin: "0.5rem 0 0.25rem" }}>Needs attention</h4>
          <ul className="check-list">
            {issues.map((c) => (
              <CheckItem key={c.rule} check={c} />
            ))}
          </ul>
        </div>
      ) : null}

      <details>
        <summary>
          Mandatory checks: {passCount} of {mandatory.length} pass
        </summary>
        <ul className="check-list">
          {[...mandatory, ...consistency].map((c) => (
            <CheckItem key={c.rule} check={c} />
          ))}
        </ul>
      </details>

      <details>
        <summary>Score breakdown (fit score {result.score_total.toFixed(1)})</summary>
        <div className="table-wrap">
          <table>
            <caption className="sr-only">Score components for {result.sme.name}</caption>
            <thead>
              <tr>
                <th scope="col">Component</th>
                <th scope="col">Weight</th>
                <th scope="col">Score</th>
                <th scope="col">Points</th>
                <th scope="col">Explanation and evidence</th>
              </tr>
            </thead>
            <tbody>
              {result.components.map((c) => (
                <tr key={c.name}>
                  <th scope="row">{c.label}</th>
                  <td>{c.weight}%</td>
                  <td>{c.score.toFixed(1)}</td>
                  <td>{c.weighted.toFixed(1)}</td>
                  <td>
                    {c.explanation}
                    <EvidenceLinks evidence={c.evidence} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      {result.info_requests.length ? (
        <div>
          <h4 style={{ margin: "0.5rem 0 0.25rem" }}>Requests sent</h4>
          <ul>
            {result.info_requests.map((r) => (
              <li key={r.id}>
                {r.kind === "information" ? "Information" : "Clarification"}: <q>{r.message}</q> -{" "}
                {r.status === "open" ? "awaiting SME" : `responded ${formatDateTime(r.responded_at)}`}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="button-row">
        <button
          type="button"
          disabled={shortlisted || busy}
          onClick={async () => {
            setBusy(true);
            try {
              await onShortlist(result.sme.slug);
            } finally {
              setBusy(false);
            }
          }}
        >
          {shortlisted ? "On shortlist" : "Shortlist"}
          <span className="sr-only"> {result.sme.name}</span>
        </button>
        <button type="button" className="secondary" onClick={() => setForm("information")}>
          Request information<span className="sr-only"> from {result.sme.name}</span>
        </button>
        <button type="button" className="secondary" onClick={() => setForm("clarification")}>
          Request clarification<span className="sr-only"> from {result.sme.name}</span>
        </button>
      </div>
      {form ? (
        <RequestForm
          key={form}
          opportunityId={opportunityId}
          result={result}
          kind={form}
          onCancel={() => setForm(null)}
          onSent={async () => {
            setForm(null);
            await onChanged();
          }}
        />
      ) : null}
    </article>
  );
}

function ShortlistPanel({
  opportunityId,
  shortlist,
  onSaved,
}: {
  opportunityId: string;
  shortlist: ShortlistEntry[];
  onSaved: () => Promise<void>;
}) {
  const [order, setOrder] = useState<ShortlistEntry[]>(shortlist);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const reasonId = useId();

  useEffect(() => setOrder(shortlist), [shortlist]);

  const changed = order.map((e) => e.sme_slug).join() !== shortlist.map((e) => e.sme_slug).join();

  function move(index: number, delta: number) {
    const next = [...order];
    const [item] = next.splice(index, 1);
    next.splice(index + delta, 0, item);
    setOrder(next);
    setSaved(null);
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!reason.trim()) {
      setError("A written reason is required to change the shortlist order.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.put(`/api/opportunities/${opportunityId}/shortlist/order`, {
        sme_slugs: order.map((o) => o.sme_slug),
        reason: reason.trim(),
      });
      setSaved("Shortlist order saved. The override and your reason are recorded in the audit log.");
      setReason("");
      await onSaved();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const engine = [...shortlist].filter((s) => s.engine_rank).sort((a, b) => (a.engine_rank ?? 0) - (b.engine_rank ?? 0));

  return (
    <section className="panel" aria-labelledby="shortlist-heading">
      <h2 id="shortlist-heading">Your shortlist ({shortlist.length})</h2>
      {order.length ? (
        <form onSubmit={save}>
          <ol className="shortlist">
            {order.map((e, i) => (
              <li key={e.sme_slug}>
                <strong>{e.sme_name}</strong>{" "}
                <span className="muted">(engine rank {e.engine_rank ? `#${e.engine_rank}` : "none"})</span>{" "}
                <StatusBadge status={e.status} />{" "}
                <button type="button" className="secondary" disabled={i === 0} onClick={() => move(i, -1)}>
                  Move up<span className="sr-only"> {e.sme_name}</span>
                </button>{" "}
                <button
                  type="button"
                  className="secondary"
                  disabled={i === order.length - 1}
                  onClick={() => move(i, 1)}
                >
                  Move down<span className="sr-only"> {e.sme_name}</span>
                </button>
              </li>
            ))}
          </ol>
          {engine.length ? (
            <p className="hint">
              Engine ranking (never changed by overrides):{" "}
              {engine.map((s) => `#${s.engine_rank} ${s.sme_name}`).join(", ")}
            </p>
          ) : null}
          {changed ? (
            <>
              <div className="field">
                <label htmlFor={reasonId}>Reason for changing the order (required, recorded in the audit log)</label>
                <textarea
                  id={reasonId}
                  rows={2}
                  aria-required="true"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
              </div>
              <div className="button-row">
                <button type="submit" disabled={busy}>
                  Save order with reason
                </button>
                <button type="button" className="secondary" onClick={() => setOrder(shortlist)}>
                  Undo
                </button>
              </div>
            </>
          ) : null}
          <Notice kind="success">{saved}</Notice>
          <Notice kind="error">{error}</Notice>
        </form>
      ) : (
        <p className="muted">No SMEs shortlisted yet. Use the Shortlist button on a result.</p>
      )}
    </section>
  );
}

function Results({ id }: { id: string }) {
  const { data, error, loading, setData, reload } = useLoad<RunPayload>(`/api/opportunities/${id}/match-runs/latest`);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  async function run() {
    setRunning(true);
    setRunError(null);
    try {
      setData(await api.post<RunPayload>(`/api/opportunities/${id}/match-runs`));
    } catch (err) {
      setRunError(errorMessage(err));
    } finally {
      setRunning(false);
    }
  }

  async function shortlist(slug: string) {
    setActionError(null);
    try {
      await api.post(`/api/opportunities/${id}/shortlist`, { sme_slug: slug });
      await reload();
    } catch (err) {
      setActionError(errorMessage(err));
    }
  }

  if (!data) return loading ? <p>Loading results…</p> : <Notice kind="error">{error}</Notice>;
  const shortlisted = new Set(data.shortlist.map((s) => s.sme_slug));

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Matching results</h1>
          <p className="muted">
            Rules decide eligibility; AI only helps with understanding capability text. A human makes every decision.
          </p>
        </div>
        <div className="button-row">
          <Link href={`/buyer/opportunities/${id}`}>Requirements and weights</Link>
          <span aria-hidden="true">·</span>
          <Link href={`/buyer/audit?opportunity_id=${id}`}>Audit log</Link>
        </div>
      </div>

      <section className="panel" aria-labelledby="run-heading">
        <h2 id="run-heading">Run</h2>
        <button type="button" onClick={run} disabled={running}>
          {running ? "Running matching…" : data.run ? "Re-run matching" : "Run matching"}
        </button>
        {data.run ? (
          <p>
            Last run {formatDateTime(data.run.run_at)} (AI mode: {data.run.ai_mode}). {data.run.counts.considered ?? 0} SMEs
            considered
            {data.run.counts.excluded_no_consent
              ? `; ${data.run.counts.excluded_no_consent} excluded because they have not consented to share their profile`
              : ""}
            .
          </p>
        ) : (
          <p className="muted">Matching has not been run yet for this opportunity.</p>
        )}
        <Notice kind="error">{runError}</Notice>
        <Notice kind="error">{actionError}</Notice>
      </section>

      {data.run ? (
        <div className="grid-results">
          <ShortlistPanel opportunityId={id} shortlist={data.shortlist} onSaved={reload} />
          {GROUPS.map((g) => (
            <section key={g.key} aria-labelledby={`group-${g.key}`}>
              <h2 id={`group-${g.key}`}>
                <StatusBadge status={g.key} suffix={` (${data.groups[g.key].length})`} />
              </h2>
              {data.groups[g.key].length ? (
                data.groups[g.key].map((r) => (
                  <ResultCard
                    key={r.sme.slug}
                    opportunityId={id}
                    result={r}
                    shortlisted={shortlisted.has(r.sme.slug)}
                    onShortlist={shortlist}
                    onChanged={reload}
                  />
                ))
              ) : (
                <p className="muted">None.</p>
              )}
            </section>
          ))}
        </div>
      ) : null}
    </>
  );
}

function ResultsRoute() {
  const params = useParams<{ id: string }>();
  return <Results id={params.id} />;
}

export default function ResultsPage() {
  return (
    <RoleGate roles={["buyer"]}>
      <ResultsRoute />
    </RoleGate>
  );
}
