"use client";

import { CircleCheck, CircleX, RotateCcw, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { Dialog } from "@/components/Dialog";
import { Eyebrow } from "@/components/Eyebrow";
import { Notice } from "@/components/Notice";
import { RoleGate } from "@/components/RoleGate";
import { SectionIndex } from "@/components/SectionIndex";
import { api, errorMessage } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { useIdentity } from "@/lib/identity";
import { useLoad } from "@/lib/useLoad";
import type { AiModeSettings, Counts, Dashboard, GroupRow } from "@/lib/types";

function CountsLine({ counts }: { counts: Counts }) {
  return (
    <ul className="stat-grid">
      <li className="stat-eligible">
        <span className="stat-label">
          <CircleCheck size={14} strokeWidth={1.5} aria-hidden="true" />
          Eligible
        </span>{" "}
        <span className="stat-num">{counts.eligible}</span>
      </li>
      <li className="stat-review">
        <span className="stat-label">
          <TriangleAlert size={14} strokeWidth={1.5} aria-hidden="true" />
          Needs Review
        </span>{" "}
        <span className="stat-num">{counts.needs_review}</span>
      </li>
      <li className="stat-fail">
        <span className="stat-label">
          <CircleX size={14} strokeWidth={1.5} aria-hidden="true" />
          Not Eligible
        </span>{" "}
        <span className="stat-num">{counts.not_eligible}</span>
      </li>
    </ul>
  );
}

function FairnessTable({ caption, rows }: { caption: string; rows: GroupRow[] }) {
  return (
    // Focusable scroll region so keyboard users can scroll the table when it overflows on narrow screens.
    <div className="table-wrap" role="region" aria-label={`Fairness: ${caption}`} tabIndex={0}>
      <table>
        <caption className="table-caption">{caption}</caption>
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
              <td className="num">{r.total}</td>
              <td className="num">{r.eligible}</td>
              <td className="num">{r.needs_review}</td>
              <td className="num">{r.not_eligible}</td>
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
      <SectionIndex n={6} label="AI mode" />
      <h2 id="ai-mode-heading">AI mode</h2>
      <fieldset>
        <legend>Where AI results come from</legend>
        <div className="radio-row">
          <input
            type="radio"
            id="mode-cached"
            name="ai-mode"
            checked={aiMode.mode === "cached"}
            disabled={busy}
            onChange={() => change("cached")}
          />
          <label htmlFor="mode-cached">Cached (default): results generated earlier by the pipeline from these exact documents</label>
        </div>
        <div className="radio-row">
          <input
            type="radio"
            id="mode-live"
            name="ai-mode"
            checked={aiMode.mode === "live"}
            disabled={busy || !aiMode.live_available}
            aria-describedby="mode-live-hint"
            onChange={() => change("live")}
          />
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
      <SectionIndex n={7} label="Reset" />
      <h2 id="reset-heading">Reset demo</h2>
      <p>Restores the seed state: Thuto with no documents, no match runs, no decisions, AI mode Cached.</p>
      <button type="button" className="danger" onClick={() => setOpen(true)}>
        <RotateCcw size={14} strokeWidth={1.5} aria-hidden="true" />
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
          <Eyebrow label="YES Admin" />
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
            <SectionIndex n={1} label="Pipeline" />
            <h2 id="pipeline-heading">Pipeline</h2>
            {data.pipeline.length ? (
              data.pipeline.map((p) => (
                <div key={p.opportunity_id}>
                  <h3>{p.title}</h3>
                  <p className="meta">
                    {p.run_count} matching run{p.run_count === 1 ? "" : "s"}
                  </p>
                  <div className="grid-2">
                    <div>
                      <span className="caption-mono">Before (first run, {formatDateTime(p.before.run_at)})</span>
                      <CountsLine counts={p.before.counts} />
                    </div>
                    <div>
                      <span className="caption-mono">After (latest run, {formatDateTime(p.after.run_at)})</span>
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
              <SectionIndex n={2} label="Readiness gaps" />
              <h2 id="gaps-heading">Top readiness gaps</h2>
              {data.readiness_gaps.length ? (
                <ol className="row-list">
                  {data.readiness_gaps.map((g, i) => (
                    <li key={g.label} className="row">
                      <div className="row-inner">
                        <span className="row-index" aria-hidden="true">
                          {String(i + 1).padStart(2, "0")}
                        </span>
                        <span className="row-body">
                          <strong>{g.label}</strong>: <span className="row-count">{g.smes}</span> SME
                          {g.smes === 1 ? "" : "s"} affected, <span className="row-count">{g.open}</span> still open
                        </span>
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="muted">No gaps recorded yet.</p>
              )}
            </section>
            <section className="panel" aria-labelledby="skills-heading">
              <SectionIndex n={3} label="Skills" />
              <h2 id="skills-heading">Frequently requested skills</h2>
              <ol className="row-list">
                {data.requested_skills.map((s, i) => (
                  <li key={s.tag} className="row">
                    <div className="row-inner">
                      <span className="row-index" aria-hidden="true">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <span className="row-body">
                        <strong>{s.label}</strong>: requested <span className="row-count">{s.count}</span> time
                        {s.count === 1 ? "" : "s"}
                      </span>
                    </div>
                  </li>
                ))}
              </ol>
            </section>
          </div>

          <section className="panel" aria-labelledby="decisions-heading">
            <SectionIndex n={4} label="Decisions" />
            <h2 id="decisions-heading">Buyer decisions</h2>
            <ul className="stat-grid">
              <li>
                <span className="stat-label">
                  Shortlisted<span className="sr-only">:</span>
                </span>{" "}
                <span className="stat-num">{data.decisions.shortlisted}</span>
              </li>
              <li>
                <span className="stat-label">
                  Information requests<span className="sr-only">:</span>
                </span>{" "}
                <span className="stat-num">{data.decisions.info_requests}</span>
              </li>
              <li>
                <span className="stat-label">
                  Overrides<span className="sr-only">:</span>
                </span>{" "}
                <span className="stat-num">{data.decisions.overrides.count}</span>
              </li>
            </ul>
            {data.decisions.overrides.items.length ? (
              <ul className="row-list" style={{ marginTop: "1.5rem" }}>
                {data.decisions.overrides.items.map((o, i) => (
                  <li key={i} className="row" style={{ padding: "1rem" }}>
                    <time className="meta" dateTime={o.at}>
                      {formatDateTime(o.at)}
                    </time>
                    , {o.actor_label}: order {o.order.join(", ")} (engine ranking{" "}
                    {o.engine_ranking.join(", ")}). Reason: <q>{o.reason}</q>
                  </li>
                ))}
              </ul>
            ) : null}
          </section>

          <section className="panel" aria-labelledby="fairness-heading">
            <SectionIndex n={5} label="Fairness" />
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
