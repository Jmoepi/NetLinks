"use client";

import { useState } from "react";
import { Dialog } from "@/components/Dialog";
import { Notice } from "@/components/Notice";
import { RoleGate } from "@/components/RoleGate";
import { api, errorMessage } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { useIdentity } from "@/lib/identity";
import { useLoad } from "@/lib/useLoad";
import type { AiModeSettings, Counts, Dashboard, GroupRow } from "@/lib/types";

function CountsLine({ counts }: { counts: Counts }) {
  return (
    <ul className="stat-row" style={{ listStyle: "none", padding: 0, margin: "0.25rem 0" }}>
      <li className="badge badge-eligible">
        <span aria-hidden="true">✓</span>Eligible {counts.eligible}
      </li>
      <li className="badge badge-review">
        <span aria-hidden="true">!</span>Needs Review {counts.needs_review}
      </li>
      <li className="badge badge-fail">
        <span aria-hidden="true">✕</span>Not Eligible {counts.not_eligible}
      </li>
    </ul>
  );
}

function FairnessTable({ caption, rows }: { caption: string; rows: GroupRow[] }) {
  return (
    <div className="table-wrap">
      <table>
        <caption style={{ textAlign: "left", fontWeight: 700, padding: "0.25rem 0" }}>{caption}</caption>
        <thead>
          <tr>
            <th scope="col">Group</th>
            <th scope="col">SMEs</th>
            <th scope="col">Eligible</th>
            <th scope="col">Needs Review</th>
            <th scope="col">Not Eligible</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.group}>
              <th scope="row">{r.label}</th>
              <td>{r.total}</td>
              <td>{r.eligible}</td>
              <td>{r.needs_review}</td>
              <td>{r.not_eligible}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AiModeControl() {
  const { aiMode, refreshAiMode } = useIdentity();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function change(mode: "cached" | "live") {
    setBusy(true);
    setError(null);
    try {
      await api.put<AiModeSettings>("/api/settings/ai-mode", { mode });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      await refreshAiMode();
      setBusy(false);
    }
  }

  if (!aiMode) return <p>Loading AI mode…</p>;
  return (
    <section className="panel" aria-labelledby="ai-mode-heading">
      <h2 id="ai-mode-heading">AI mode</h2>
      <fieldset>
        <legend>Where AI results come from</legend>
        <div>
          <input
            type="radio"
            id="mode-cached"
            name="ai-mode"
            checked={aiMode.mode === "cached"}
            disabled={busy}
            onChange={() => change("cached")}
          />{" "}
          <label htmlFor="mode-cached">Cached (default): results generated earlier by the pipeline from these exact documents</label>
        </div>
        <div>
          <input
            type="radio"
            id="mode-live"
            name="ai-mode"
            checked={aiMode.mode === "live"}
            disabled={busy || !aiMode.live_available}
            aria-describedby="mode-live-hint"
            onChange={() => change("live")}
          />{" "}
          <label htmlFor="mode-live">Live: run Amazon Bedrock now</label>
          <p id="mode-live-hint" className="hint">
            {aiMode.live_available
              ? `Extraction model ${aiMode.extraction_model_id ?? "(not set)"}, embeddings ${aiMode.embedding_model_id ?? "(not set)"}.`
              : `Live mode is unavailable: ${aiMode.live_unavailable_reason ?? "Bedrock is not configured"}. Cached mode keeps the demo independent of venue Wi-Fi.`}
          </p>
        </div>
      </fieldset>
      <Notice kind="error">{error}</Notice>
    </section>
  );
}

function ResetControl() {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function reset() {
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/admin/reset");
      window.location.reload();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="reset-heading">
      <h2 id="reset-heading">Reset demo</h2>
      <p>Restores the seed state: Thuto with no documents, no match runs, no decisions, AI mode Cached.</p>
      <button type="button" className="danger" onClick={() => setOpen(true)}>
        Reset demo
      </button>
      <Notice kind="error">{error}</Notice>
      <Dialog
        open={open}
        title="Reset the demo?"
        onClose={() => setOpen(false)}
        actions={
          <>
            <button type="button" className="danger" disabled={busy} onClick={reset}>
              {busy ? "Resetting…" : "Yes, reset the demo"}
            </button>
            <button type="button" className="secondary" disabled={busy} onClick={() => setOpen(false)}>
              Cancel
            </button>
          </>
        }
      >
        <p>
          This deletes uploaded documents, match runs, shortlists, requests and audit entries, then reloads the fictional
          seed data.
        </p>
      </Dialog>
    </section>
  );
}

function DashboardView() {
  const { data, error, loading, reload } = useLoad<Dashboard>("/api/admin/dashboard");

  return (
    <>
      <div className="page-header">
        <div>
          <h1>YES dashboard</h1>
          <p className="muted">Where to aim support: pipeline outcomes, readiness gaps and demand for skills.</p>
        </div>
        <button type="button" className="secondary" onClick={() => void reload()}>
          Refresh
        </button>
      </div>
      {!data ? (
        loading ? (
          <p>Loading dashboard…</p>
        ) : (
          <Notice kind="error">{error}</Notice>
        )
      ) : (
        <>
          <section className="panel" aria-labelledby="pipeline-heading">
            <h2 id="pipeline-heading">Pipeline</h2>
            {data.pipeline.length ? (
              data.pipeline.map((p) => (
                <div key={p.opportunity_id}>
                  <h3>{p.title}</h3>
                  <p className="muted">{p.run_count} matching run{p.run_count === 1 ? "" : "s"}</p>
                  <div className="grid-2">
                    <div>
                      <strong>Before (first run, {formatDateTime(p.before.run_at)})</strong>
                      <CountsLine counts={p.before.counts} />
                    </div>
                    <div>
                      <strong>After (latest run, {formatDateTime(p.after.run_at)})</strong>
                      <CountsLine counts={p.after.counts} />
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <p className="muted">No matching runs yet.</p>
            )}
          </section>

          <div className="grid-2">
            <section className="panel" aria-labelledby="gaps-heading">
              <h2 id="gaps-heading">Top readiness gaps</h2>
              {data.readiness_gaps.length ? (
                <ol>
                  {data.readiness_gaps.map((g) => (
                    <li key={g.label}>
                      <strong>{g.label}</strong>: {g.smes} SME{g.smes === 1 ? "" : "s"} affected, {g.open} still open
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="muted">No gaps recorded yet.</p>
              )}
            </section>
            <section className="panel" aria-labelledby="skills-heading">
              <h2 id="skills-heading">Frequently requested skills</h2>
              <ol>
                {data.requested_skills.map((s) => (
                  <li key={s.tag}>
                    <strong>{s.label}</strong>: requested {s.count} time{s.count === 1 ? "" : "s"}
                  </li>
                ))}
              </ol>
            </section>
          </div>

          <section className="panel" aria-labelledby="decisions-heading">
            <h2 id="decisions-heading">Buyer decisions</h2>
            <p>
              Shortlisted: {data.decisions.shortlisted} · Information requests: {data.decisions.info_requests} · Overrides:{" "}
              {data.decisions.overrides.count}
            </p>
            {data.decisions.overrides.items.length ? (
              <ul>
                {data.decisions.overrides.items.map((o, i) => (
                  <li key={i}>
                    {formatDateTime(o.at)}, {o.actor_label}: order {o.order.join(", ")} (engine ranking{" "}
                    {o.engine_ranking.join(", ")}). Reason: <q>{o.reason}</q>
                  </li>
                ))}
              </ul>
            ) : null}
          </section>

          <section className="panel" aria-labelledby="fairness-heading">
            <h2 id="fairness-heading">Fairness view: outcomes by province and business size</h2>
            <p className="notice notice-info" role="note">
              {data.fairness?.note || "Small sample: shows the mechanism, not a finding."}
            </p>
            {data.fairness && data.fairness.run_id ? (
              <div className="grid-2">
                <FairnessTable caption="By province" rows={data.fairness.by_province} />
                <FairnessTable caption="By business size" rows={data.fairness.by_size_band} />
              </div>
            ) : (
              <p className="muted">Run matching to populate the fairness view.</p>
            )}
          </section>
        </>
      )}
      <div className="grid-2">
        <AiModeControl />
        <ResetControl />
      </div>
    </>
  );
}

export default function AdminPage() {
  return (
    <RoleGate roles={["admin"]}>
      <DashboardView />
    </RoleGate>
  );
}
