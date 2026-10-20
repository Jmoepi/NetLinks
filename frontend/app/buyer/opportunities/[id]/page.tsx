"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useId, useState, type FormEvent } from "react";
import { Notice } from "@/components/Notice";
import { RoleGate } from "@/components/RoleGate";
import { api, errorMessage } from "@/lib/api";
import { formatDateTime, rand } from "@/lib/format";
import { useLoad } from "@/lib/useLoad";
import type { AuditEntry, Criterion, OpportunityDetail, StructureResult, Weights } from "@/lib/types";

const RULE_LABELS: Record<string, string> = {
  tax_compliance: "Valid tax compliance status (expiry after the closing date)",
  csd_registration: "CSD registration number (present and correctly formatted)",
  ownership_or_bbbee: "Black ownership or B-BBEE level",
  operating_region: "Operates in the required province",
  pi_insurance: "Professional indemnity insurance, current at closing",
  infosec_policy: "Information security & POPIA policy provided",
  certified_technicians: "Technicians with current certifications",
  capability: "Capability (service desk, device support, Microsoft 365)",
  experience: "Experience and comparable clients",
  capacity: "Capacity: technicians and service desk hours",
  location: "Location: on-site response distance",
};

const PARAM_LABELS: Record<string, string> = {
  min_black_ownership_pct: "Minimum Black ownership (%)",
  max_bbbee_level: "Highest accepted B-BBEE level",
  region: "Province code (e.g. GP for Gauteng)",
  min_amount: "Minimum cover (Rand)",
  min_count: "Minimum number of certified technicians",
  text: "Capability description used for semantic matching",
  tags: "Structured capability tags",
  min_years: "Preferred minimum years trading",
  min_client_users: "Comparable client size (users)",
  min_technicians: "Preferred number of technicians",
  hours_start: "Service desk hours from",
  hours_end: "Service desk hours to",
  anchor: "Anchor site",
  full_score_km: "Full score within (km)",
  zero_score_km: "Zero score beyond (km)",
};

const WEIGHT_LABELS: Record<keyof Weights, string> = {
  capability: "Capability",
  experience: "Experience",
  capacity: "Capacity",
  location: "Location",
};

const WEIGHT_KEYS: (keyof Weights)[] = ["capability", "experience", "capacity", "location"];

function ParamInput({
  name,
  value,
  onChange,
}: {
  name: string;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  const id = useId();
  const label = PARAM_LABELS[name] || name;
  if (Array.isArray(value)) {
    return (
      <div className="field">
        <span id={id} style={{ fontWeight: 600 }}>
          {label}
        </span>
        <span aria-labelledby={id}>{value.map((v) => String(v).replace(/_/g, " ")).join(", ")}</span>
      </div>
    );
  }
  if (name === "text") {
    return (
      <div className="field" style={{ flexBasis: "100%" }}>
        <label htmlFor={id}>{label}</label>
        <textarea id={id} rows={2} value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} />
        <span className="hint">Changing this text needs new embeddings, so matching then requires Live AI mode.</span>
      </div>
    );
  }
  const numeric = typeof value === "number" || value === "";
  const isTime = name.startsWith("hours_");
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type={isTime ? "time" : numeric ? "number" : "text"}
        min={numeric ? 0 : undefined}
        value={value === null || value === undefined ? "" : String(value)}
        onChange={(e) => onChange(numeric ? (e.target.value === "" ? "" : Number(e.target.value)) : e.target.value)}
        aria-describedby={name === "min_amount" ? `${id}-hint` : undefined}
      />
      {name === "min_amount" && typeof value === "number" ? (
        <span id={`${id}-hint`} className="hint">
          {rand(value)}
        </span>
      ) : null}
    </div>
  );
}

function CriteriaEditor({
  title,
  criteria,
  onChange,
}: {
  title: string;
  criteria: Criterion[];
  onChange: (next: Criterion[]) => void;
}) {
  function setParam(index: number, key: string, value: unknown) {
    onChange(criteria.map((c, i) => (i === index ? { ...c, params: { ...c.params, [key]: value } } : c)));
  }
  return (
    <section className="panel" aria-label={title}>
      <h2>{title}</h2>
      {criteria.map((c, i) => (
        <fieldset key={c.rule_type}>
          <legend>{RULE_LABELS[c.rule_type] || c.rule_type}</legend>
          {c.source_quote ? (
            <p className="hint">
              From the RFQ: <q>{c.source_quote}</q>
            </p>
          ) : null}
          {Object.keys(c.params).length ? (
            <div className="field-inline">
              {Object.entries(c.params).map(([k, v]) => (
                <ParamInput key={k} name={k} value={v} onChange={(nv) => setParam(i, k, nv)} />
              ))}
            </div>
          ) : (
            <p className="muted" style={{ margin: 0 }}>
              No settings: checked as a plain rule.
            </p>
          )}
        </fieldset>
      ))}
    </section>
  );
}

function Editor({ id }: { id: string }) {
  const { data, error, loading, setData } = useLoad<OpportunityDetail>(`/api/opportunities/${id}`);
  const [rfq, setRfq] = useState("");
  const [mandatory, setMandatory] = useState<Criterion[]>([]);
  const [preferred, setPreferred] = useState<Criterion[]>([]);
  const [weights, setWeights] = useState<Record<keyof Weights, number | "">>({
    capability: 40,
    experience: 25,
    capacity: 20,
    location: 15,
  });
  const [proposal, setProposal] = useState<StructureResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [changes, setChanges] = useState<string[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const rfqId = useId();

  useEffect(() => {
    if (!data) return;
    setRfq(data.raw_rfq_text);
    setMandatory(data.mandatory_criteria);
    setPreferred(data.preferred_criteria);
    setWeights({ ...data.weights });
  }, [data]);

  if (!data) return loading ? <p>Loading opportunity…</p> : <Notice kind="error">{error}</Notice>;

  const sum = WEIGHT_KEYS.reduce((acc, k) => acc + (Number(weights[k]) || 0), 0);
  const weightsValid = sum === 100 && WEIGHT_KEYS.every((k) => Number.isInteger(weights[k]) && Number(weights[k]) >= 0);

  async function structure() {
    setBusy(true);
    setErr(null);
    setMessage(null);
    setChanges([]);
    try {
      const res = await api.post<StructureResult>(`/api/opportunities/${id}/structure-rfq`, { raw_text: rfq });
      setProposal(res);
      setMandatory(res.proposal.mandatory_criteria);
      setPreferred(res.proposal.preferred_criteria);
      setMessage("AI proposal loaded into the editor. It is not saved until you click Save requirements.");
    } catch (e) {
      setErr(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!weightsValid) {
      setErr(`Weights must be whole numbers that sum to 100 (currently ${sum}).`);
      return;
    }
    setBusy(true);
    setErr(null);
    setMessage(null);
    try {
      const saved = await api.put<OpportunityDetail>(`/api/opportunities/${id}`, {
        mandatory_criteria: mandatory,
        preferred_criteria: preferred,
        weights,
        proposal_ai_result_id: proposal?.ai_result_id ?? null,
      });
      setData(saved);
      setProposal(null);
      setMessage("Requirements saved. The change is recorded in the audit log.");
      try {
        const audit = await api.get<{ entries: AuditEntry[] }>(`/api/audit?opportunity_id=${id}`);
        const last = [...audit.entries].reverse().find((a) => a.action === "requirement_edit");
        const d = (last?.details || {}) as {
          changes_vs_proposal?: { summary: string }[] | null;
          changes_vs_previous?: { summary: string }[];
        };
        const list = d.changes_vs_proposal ?? d.changes_vs_previous ?? [];
        setChanges(list.map((c) => (d.changes_vs_proposal ? `${c.summary} (vs AI proposal)` : c.summary)));
      } catch {
        // the save succeeded; the change summary is optional
      }
    } catch (e2) {
      setErr(errorMessage(e2));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Requirements</h1>
          <p className="muted">{data.title}</p>
          <p className="muted">
            Closes {data.closing_date} · contract starts {data.contract_start}
          </p>
        </div>
        <Link href={`/buyer/opportunities/${id}/results`}>Go to matching results</Link>
      </div>

      <section className="panel" aria-labelledby="rfq-heading">
        <h2 id="rfq-heading">RFQ text</h2>
        <div className="field">
          <label htmlFor={rfqId}>Raw RFQ text (paste the buyer&apos;s request)</label>
          <textarea id={rfqId} rows={10} value={rfq} onChange={(e) => setRfq(e.target.value)} />
        </div>
        <div className="button-row">
          <button type="button" onClick={structure} disabled={busy}>
            {busy ? "Working…" : "Structure requirements"}
          </button>
        </div>
        <p className="hint">
          The AI proposes mandatory and preferred criteria from a fixed rule catalogue. Mandatory rules then run as plain
          code: same input, same answer, every time.
        </p>
        {proposal ? (
          <Notice kind="info">
            AI proposal (unsaved): {proposal.cache_hit ? "cached result" : "live result"} from {proposal.provider} ·{" "}
            model {proposal.model_id} · generated by {proposal.generated_by} · {formatDateTime(proposal.generated_at)}
          </Notice>
        ) : null}
      </section>

      <form onSubmit={save}>
        <CriteriaEditor title="Mandatory criteria (pass / needs review / fail)" criteria={mandatory} onChange={setMandatory} />
        <CriteriaEditor title="Preferred criteria (scored)" criteria={preferred} onChange={setPreferred} />

        <section className="panel" aria-labelledby="weights-heading">
          <h2 id="weights-heading">Fit weights</h2>
          <p className="hint">Visible, editable settings. Whole numbers that must add up to 100.</p>
          <div className="field-inline">
            {WEIGHT_KEYS.map((k) => (
              <div className="field" key={k}>
                <label htmlFor={`weight-${k}`}>{WEIGHT_LABELS[k]} (%)</label>
                <input
                  id={`weight-${k}`}
                  type="number"
                  min={0}
                  max={100}
                  step={1}
                  value={weights[k]}
                  aria-describedby="weights-sum"
                  onChange={(e) =>
                    setWeights({ ...weights, [k]: e.target.value === "" ? "" : Number(e.target.value) })
                  }
                />
              </div>
            ))}
          </div>
          <p id="weights-sum" className={weightsValid ? "notice notice-success" : "notice notice-error"} aria-live="polite">
            Total: {sum} / 100{weightsValid ? " ✓" : " - weights must sum to 100"}
          </p>
        </section>

        <div className="button-row">
          <button type="submit" disabled={busy || !weightsValid}>
            Save requirements
          </button>
        </div>
        <Notice kind="success">{message}</Notice>
        {changes.length ? (
          <div className="notice notice-info" role="status">
            Recorded in the audit log:
            <ul>
              {changes.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </div>
        ) : null}
        <Notice kind="error">{err}</Notice>
      </form>
    </>
  );
}

function EditorRoute() {
  const params = useParams<{ id: string }>();
  return <Editor id={params.id} />;
}

export default function OpportunityEditorPage() {
  return (
    <RoleGate roles={["buyer"]}>
      <EditorRoute />
    </RoleGate>
  );
}
