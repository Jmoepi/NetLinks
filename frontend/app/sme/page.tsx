"use client";

import { ArrowRight, ArrowUpRight, CircleCheck, EqualNot, FileText, Minus, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { Suspense, useId, useState, type FormEvent } from "react";
import { Dialog } from "@/components/Dialog";
import { Eyebrow } from "@/components/Eyebrow";
import { Notice } from "@/components/Notice";
import { Pagination } from "@/components/Pagination";
import { RoleGate } from "@/components/RoleGate";
import { SectionIndex } from "@/components/SectionIndex";
import { SourceBadge } from "@/components/SourceBadge";
import { UploadForm } from "@/components/UploadForm";
import { api, errorMessage } from "@/lib/api";
import { confidenceText, docTypeLabel, formatDateTime, formatValue, INTEGER_FIELDS, sourceHref } from "@/lib/format";
import { pageSlice, usePageParam } from "@/lib/pagination";
import { useLoad } from "@/lib/useLoad";
import type { Candidate, Profile, ProfileField, Sme } from "@/lib/types";

const DOCS_PAGE_SIZE = 10;

type EditMode = "integer" | "text" | "list" | "json";

function editModeFor(field: ProfileField): EditMode {
  if (INTEGER_FIELDS.has(field.field_key)) return "integer";
  const v = field.value;
  if (Array.isArray(v)) return v.every((x) => typeof x === "string") ? "list" : "json";
  if (v && typeof v === "object") return "json";
  if (field.field_key === "certifications" || field.field_key === "past_clients" || field.field_key === "service_desk_hours")
    return "json";
  if (field.field_key === "service_regions" || field.field_key === "service_tags") return "list";
  return "text";
}

function initialText(field: ProfileField, mode: EditMode): string {
  const v = field.value;
  if (v === null || v === undefined) return "";
  if (mode === "list" && Array.isArray(v)) return v.join(", ");
  if (mode === "json") return JSON.stringify(v, null, 2);
  return String(v);
}

function parseValue(text: string, mode: EditMode): unknown {
  if (mode === "integer") {
    const n = Number(text.replace(/[\s,R]/g, ""));
    if (!Number.isInteger(n) || n < 0) throw new Error("Enter a whole number (for example 11 or 2000000).");
    return n;
  }
  if (mode === "list") return text.split(",").map((s) => s.trim()).filter(Boolean);
  if (mode === "json") {
    try {
      return JSON.parse(text);
    } catch {
      throw new Error("Enter valid JSON for this structured field.");
    }
  }
  return text.trim();
}

function SourceLink({ c }: { c: Candidate }) {
  const href = sourceHref(c);
  if (!href) return <span className="muted">{c.source_label || "SME entry"}</span>;
  return (
    <Link href={href} className="link-arrow">
      View source<span className="sr-only"> for {c.field_key} in {c.source_label}</span>
      <ArrowUpRight size={14} strokeWidth={1.5} aria-hidden="true" />
    </Link>
  );
}

function FieldRow({ field, onChanged }: { field: ProfileField; onChanged: () => Promise<void> }) {
  const [editing, setEditing] = useState(false);
  const mode = editModeFor(field);
  const [text, setText] = useState(() => initialText(field, mode));
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const valueId = useId();
  const noteId = useId();

  async function save(e: FormEvent) {
    e.preventDefault();
    setError(null);
    let value: unknown;
    try {
      value = parseValue(text, mode);
    } catch (err) {
      setError(errorMessage(err));
      return;
    }
    setBusy(true);
    try {
      await api.patch(`/api/sme/me/profile/fields/${field.field_key}`, { value, note: note.trim() || null });
      setEditing(false);
      await onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function confirm(candidateId?: number) {
    setBusy(true);
    setError(null);
    try {
      await api.post(
        `/api/sme/me/profile/fields/${field.field_key}/confirm`,
        candidateId ? { candidate_id: candidateId } : undefined,
      );
      await onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const rowClass = field.conflict
    ? "row-conflict"
    : field.low_confidence
      ? "row-low-confidence"
      : field.status === "missing"
        ? "row-missing"
        : "";
  const canConfirm = field.source_type === "ai_extracted" && !field.conflict && field.status !== "missing";

  return (
    <tr className={rowClass}>
      <th scope="row">{field.label}</th>
      <td>
        {field.conflict ? (
          <div>
            <strong>Conflicting values - choose the correct one:</strong>
            <ul className="evidence-list">
              {field.candidates.map((c) => (
                <li key={c.id}>
                  {formatValue(field.field_key, c.value)} <span className="muted">from {c.source_label}</span>{" "}
                  <SourceBadge source={c.source_type} /> <SourceLink c={c} />{" "}
                  <button type="button" className="secondary" disabled={busy} onClick={() => confirm(c.id)}>
                    Confirm this value<span className="sr-only"> ({formatValue(field.field_key, c.value)})</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <span>{formatValue(field.field_key, field.value)}</span>
        )}
        {field.low_confidence ? (
          <span className="flag-text">
            <TriangleAlert size={14} strokeWidth={1.5} aria-hidden="true" />
            Low confidence - please confirm
          </span>
        ) : null}
        {field.selected?.quote && !field.conflict ? (
          <span className="hint" style={{ display: "block" }}>
            Source text: <q>{field.selected.quote}</q>
          </span>
        ) : null}
        {field.selected?.note ? <span className="hint" style={{ display: "block" }}>Note: {field.selected.note}</span> : null}
        {editing ? (
          <form onSubmit={save} className="panel" style={{ marginTop: "0.5rem" }}>
            <div className="field">
              <label htmlFor={valueId}>New value for {field.label}</label>
              {mode === "json" ? (
                <textarea id={valueId} rows={5} value={text} onChange={(e) => setText(e.target.value)} />
              ) : (
                <input
                  id={valueId}
                  type={mode === "integer" ? "number" : "text"}
                  min={mode === "integer" ? 0 : undefined}
                  step={mode === "integer" ? 1 : undefined}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                />
              )}
              {mode === "list" ? <span className="hint">Separate items with commas.</span> : null}
            </div>
            <div className="field">
              <label htmlFor={noteId}>Note (optional, recorded in the audit log)</label>
              <input id={noteId} type="text" value={note} onChange={(e) => setNote(e.target.value)} />
            </div>
            <div className="button-row">
              <button type="submit" disabled={busy}>
                Save correction
              </button>
              <button type="button" className="secondary" onClick={() => setEditing(false)}>
                Cancel
              </button>
            </div>
          </form>
        ) : null}
        <Notice kind="error">{error}</Notice>
      </td>
      <td>
        {field.status === "missing" ? (
          <span className="muted">Not provided</span>
        ) : field.conflict ? (
          <span className="badge badge-fail">
            <EqualNot size={14} strokeWidth={1.5} aria-hidden="true" />
            Conflict
          </span>
        ) : (
          <>
            <SourceBadge source={field.source_type} /> {field.low_confidence ? <SourceBadge source="low_confidence" /> : null}
          </>
        )}
      </td>
      <td className="num">{field.status === "missing" || field.conflict ? "-" : confidenceText(field.confidence)}</td>
      <td>{field.selected && !field.conflict ? <SourceLink c={field.selected} /> : null}</td>
      <td>
        <div className="button-row" style={{ marginTop: 0 }}>
          {!editing ? (
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setText(initialText(field, mode));
                setEditing(true);
              }}
            >
              Edit<span className="sr-only"> {field.label}</span>
            </button>
          ) : null}
          {canConfirm ? (
            <button type="button" disabled={busy} onClick={() => confirm()}>
              Confirm<span className="sr-only"> {field.label}</span>
            </button>
          ) : null}
        </div>
      </td>
    </tr>
  );
}

function ConsentPanel({ sme, onAnswered }: { sme: Sme; onAnswered: () => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function answer(granted: boolean) {
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/sme/me/consent", { granted });
      setOpen(false);
      await onAnswered();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const status = sme.consent_status || "pending";
  return (
    <section className="panel" aria-labelledby="consent-heading">
      <SectionIndex n={3} label="Sharing" />
      <h2 id="consent-heading">Sharing with buyers</h2>
      {status === "granted" ? (
        <p>
          <span className="badge badge-eligible">
            <CircleCheck size={14} strokeWidth={1.5} aria-hidden="true" />
            Shared with buyers
          </span>{" "}
          Consent given {formatDateTime(sme.consent_at)}. Buyers on NetLinks can see this profile and include it in matching.
        </p>
      ) : status === "declined" ? (
        <p>
          <span className="badge badge-neutral">
            <Minus size={14} strokeWidth={1.5} aria-hidden="true" />
            Not shared
          </span> You declined sharing, so buyers cannot see this profile and
          it is excluded from matching.
        </p>
      ) : (
        <p>Your profile is private until you choose to share it. Unshared profiles are never included in matching.</p>
      )}
      <div className="button-row">
        <button type="button" onClick={() => setOpen(true)}>
          {status === "pending" ? "I've reviewed my profile - choose sharing" : "Change sharing choice"}
        </button>
      </div>
      <Dialog
        open={open}
        title="Share this profile with buyers on NetLinks?"
        onClose={() => setOpen(false)}
        actions={
          <>
            <button type="button" disabled={busy} onClick={() => answer(true)}>
              Accept and share
            </button>
            <button type="button" className="secondary" disabled={busy} onClick={() => answer(false)}>
              Decline
            </button>
          </>
        }
      >
        <p>
          Buyers will see your confirmed profile, the source documents behind each value, and how you match their
          opportunities. You can change this choice later. Every choice is recorded in the audit log.
        </p>
        <Notice kind="error">{error}</Notice>
      </Dialog>
    </section>
  );
}

function SmeProfile() {
  const { data, error, loading, reload } = useLoad<Profile>("/api/sme/me/profile");
  const { page: docsPage, setPage: setDocsPage } = usePageParam("docs_page");
  const [sort, setSort] = useState<{ key: "confidence" | "field"; dir: "asc" | "desc" }>({ key: "confidence", dir: "asc" });

  if (!data) return loading ? <p>Loading profile…</p> : <Notice kind="error">{error}</Notice>;

  const sortedFields = [...data.fields].sort((a, b) => {
    if (sort.key === "confidence") {
      const rank = (f: ProfileField) =>
        f.conflict || f.status === "missing" ? Number.POSITIVE_INFINITY : (f.confidence ?? Number.NEGATIVE_INFINITY);
      const av = rank(a);
      const bv = rank(b);
      if (av === bv) return 0;
      const cmp = av < bv ? -1 : 1;
      return sort.dir === "asc" ? cmp : -cmp;
    }
    const cmp = a.label.localeCompare(b.label);
    return sort.dir === "asc" ? cmp : -cmp;
  });
  const docs = pageSlice(data.documents, docsPage, DOCS_PAGE_SIZE);
  const activeDocs = data.documents.filter((d) => !d.superseded_by_document_id);
  const needsAttention = data.low_confidence.length + data.conflicts.length;
  const nextStep =
    data.documents.length === 0
      ? {
          href: "#upload-heading",
          action: "Upload a document",
          detail: "Start with a capability statement, certificate or policy so NetLinks can build your evidence-backed profile.",
        }
      : needsAttention > 0
        ? {
            href: "#profile-heading",
            action: `Review ${needsAttention} field${needsAttention === 1 ? "" : "s"}`,
            detail: "Confirm low-confidence or conflicting information before you share your profile with buyers.",
          }
        : data.sme.consent_status !== "granted"
          ? {
              href: "#consent-heading",
              action: "Choose profile sharing",
              detail: "Your profile remains private until you decide whether buyers can include it in matching.",
            }
          : {
              href: "/sme/readiness",
              action: "Check my readiness",
              detail: "See buyer requests, current opportunity status and the next evidence that could help you qualify.",
            };

  return (
    <>
      <div className="page-header">
        <div>
          <Eyebrow label="SME workspace" />
          <h1>{data.sme.name}</h1>
          <p className="meta">
            {data.sme.base_town} · {data.sme.size_band} business · SME profile
          </p>
        </div>
        <Link href="/sme/readiness" className="link-arrow">
          Go to readiness and buyer requests
          <ArrowRight size={16} strokeWidth={1.5} aria-hidden="true" />
        </Link>
      </div>

      <section className="panel journey-next" aria-labelledby="next-step-heading">
        <p className="section-index">Next step</p>
        <h2 id="next-step-heading">{nextStep.action}</h2>
        <p className="muted">{nextStep.detail}</p>
        <Link href={nextStep.href} className="button-link">
          {nextStep.action}
          <ArrowRight size={16} strokeWidth={1.5} aria-hidden="true" />
        </Link>
      </section>

      <section className="panel" aria-labelledby="upload-heading">
        <SectionIndex n={1} label="Upload" />
        <h2 id="upload-heading">1. Upload your documents</h2>
        <UploadForm onUploaded={() => void reload()} />
        {data.documents.length ? (
          <>
            <h3>Your documents</h3>
            <ul className="row-list">
              {docs.items.map((d, i) => (
                <li key={d.id} className="row">
                  <div className="row-inner">
                    <span className="row-index" aria-hidden="true">
                      {String(docs.offset + i + 1).padStart(2, "0")}
                    </span>
                    <span className="doc-row">
                      <FileText size={16} strokeWidth={1.5} aria-hidden="true" />
                      <Link href={`/documents/${d.id}`}>{d.filename}</Link>
                      <span className="muted">
                        - {docTypeLabel(d.doc_type)}
                        {d.period_end ? `, valid to ${d.period_end}` : ""}
                        {d.superseded_by_document_id ? " (replaced by a newer document)" : ""}
                      </span>
                    </span>
                  </div>
                </li>
              ))}
            </ul>
            <Pagination
              label="Documents"
              page={docs.page}
              pageSize={DOCS_PAGE_SIZE}
              total={data.documents.length}
              onPageChange={setDocsPage}
            />
          </>
        ) : (
          <p className="muted">No documents uploaded yet.</p>
        )}
      </section>

      <section className="panel" aria-labelledby="profile-heading">
        <SectionIndex n={2} label="Profile" />
        <h2 id="profile-heading">2. Review your extracted profile</h2>
        <p>
          AI suggests, you confirm. Each value shows where it came from. Nothing is treated as verified just because a model
          read it.
        </p>
        {activeDocs.length && needsAttention ? (
          <Notice kind="info">
            {needsAttention} field{needsAttention > 1 ? "s need" : " needs"} your attention (low confidence or conflicting
            sources).
          </Notice>
        ) : null}
        <div className="field-inline">
          <div className="field">
            <label htmlFor="profile-field-sort">Sort profile fields</label>
            <select
              id="profile-field-sort"
              value={`${sort.key}:${sort.dir}`}
              onChange={(e) => {
                const parts = e.target.value.split(":");
                const key = parts[0] === "field" ? "field" : "confidence";
                const dir = parts[1] === "desc" ? "desc" : "asc";
                setSort({ key, dir });
              }}
            >
              <option value="confidence:asc">Lowest confidence first</option>
              <option value="confidence:desc">Highest confidence first</option>
              <option value="field:asc">Field A-Z</option>
            </select>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <caption className="sr-only">Extracted profile fields with source and confidence</caption>
            <thead>
              <tr>
                <th scope="col">Field</th>
                <th scope="col">Value</th>
                <th scope="col">Source</th>
                <th scope="col">Confidence</th>
                <th scope="col">Evidence</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sortedFields.map((f) => (
                <FieldRow
                  key={`${f.field_key}-${f.selected?.id ?? "none"}-${f.candidates.length}`}
                  field={f}
                  onChanged={reload}
                />
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <ConsentPanel sme={data.sme} onAnswered={reload} />
    </>
  );
}

export default function SmePage() {
  return (
    <RoleGate roles={["sme"]}>
      <Suspense fallback={<p>Loading profile…</p>}>
        <SmeProfile />
      </Suspense>
    </RoleGate>
  );
}
