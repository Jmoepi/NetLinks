"use client";

import { ArrowLeft, CircleCheck, Hourglass } from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";
import { Eyebrow } from "@/components/Eyebrow";
import { Notice } from "@/components/Notice";
import { Pagination } from "@/components/Pagination";
import { RoleGate } from "@/components/RoleGate";
import { SectionIndex } from "@/components/SectionIndex";
import { StatusBadge } from "@/components/StatusBadge";
import { UploadForm } from "@/components/UploadForm";
import { formatDateTime } from "@/lib/format";
import { pageSlice, usePageParam } from "@/lib/pagination";
import { useLoad } from "@/lib/useLoad";
import type { Readiness } from "@/lib/types";

const REQUESTS_PAGE_SIZE = 10;

function ReadinessView() {
  const { data, error, loading, reload } = useLoad<Readiness>("/api/sme/me/readiness");
  const { page: requestsPage, setPage: setRequestsPage } = usePageParam("requests_page");

  if (!data) return loading ? <p>Loading readiness…</p> : <Notice kind="error">{error}</Notice>;

  const openRequests = data.requests.filter((r) => r.status === "open");
  const requests = pageSlice(data.requests, requestsPage, REQUESTS_PAGE_SIZE);

  return (
    <>
      <div className="page-header">
        <div>
          <Eyebrow label="SME readiness" />
          <h1>Readiness: {data.sme.name}</h1>
          <p className="muted">Buyer requests and what would help you qualify. Guidance never changes a current ranking.</p>
        </div>
        <Link href="/sme" className="link-arrow">
          <ArrowLeft size={16} strokeWidth={1.5} aria-hidden="true" />
          Back to my profile
        </Link>
      </div>

      <section className="panel" aria-labelledby="requests-heading">
        <SectionIndex n={1} label="Requests" />
        <h2 id="requests-heading">Buyer requests ({openRequests.length} open)</h2>
        {data.requests.length ? (
          <ul className="row-list">
            {requests.items.map((r, i) => (
              <li key={r.id} className="row">
                <div className="row-inner">
                <span className="row-index" aria-hidden="true">
                  {String(requests.offset + i + 1).padStart(2, "0")}
                </span>
                <div className="row-body">
                <strong>{r.kind === "information" ? "Request for information" : "Request for clarification"}</strong> from{" "}
                {r.buyer_org} ({formatDateTime(r.created_at)}): <q>{r.message}</q>{" "}
                {r.status === "open" ? (
                  <span className="badge badge-awaiting">
                    <Hourglass size={14} strokeWidth={1.5} aria-hidden="true" />
                    Open - awaiting your response
                  </span>
                ) : (
                  <span className="badge badge-eligible">
                    <CircleCheck size={14} strokeWidth={1.5} aria-hidden="true" />
                    Responded {formatDateTime(r.responded_at)}
                  </span>
                )}
                </div>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No buyer requests yet.</p>
        )}
        <Pagination
          label="Buyer requests"
          page={requests.page}
          pageSize={REQUESTS_PAGE_SIZE}
          total={data.requests.length}
          onPageChange={setRequestsPage}
        />
      </section>

      <section className="panel" aria-labelledby="reupload-heading">
        <SectionIndex n={2} label="Upload" />
        <h2 id="reupload-heading">Upload new or renewed documents</h2>
        <p>Uploading answers your open buyer requests. The buyer re-runs matching to see the update.</p>
        <UploadForm label="Upload renewed documents (PDF)" buttonText="Upload" onUploaded={() => void reload()} />
      </section>

      {data.opportunities.map((o, oi) => {
        const issues = o.checks.filter((c) => c.outcome !== "pass");
        return (
          <section className="panel" key={o.opportunity_id} aria-labelledby={`opp-${o.opportunity_id}`}>
            <SectionIndex n={3 + oi} label="Opportunity" />
            <h2 id={`opp-${o.opportunity_id}`}>{o.title}</h2>
            <p className="meta">
              {o.buyer_org} · closes {o.closing_date}
            </p>
            <p>
              Current status: <StatusBadge status={o.status} />{" "}
              {o.awaiting_sme ? <StatusBadge status="awaiting_sme" /> : null}
              {o.run_at ? <span className="muted"> (assessed {formatDateTime(o.run_at)})</span> : null}
            </p>
            {issues.length ? (
              <>
                <h3>Why</h3>
                <ul className="check-list">
                  {issues.map((c) => (
                    <li key={c.rule}>
                      <StatusBadge status={c.outcome} /> <strong>{c.label}:</strong> {c.reason}
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
            <h3>Readiness actions</h3>
            {o.actions.length ? (
              <ul className="row-list">
                {o.actions.map((a, i) => (
                  <li key={`${a.category}-${i}`} className="row">
                    <div className="row-inner">
                      <span className="row-index" aria-hidden="true">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <span className="row-body">{a.text}</span>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">{o.run_id ? "No actions: nothing is holding you back here." : "Not assessed yet."}</p>
            )}
            <p className="hint">Readiness actions help you qualify next time. They do not change the current ranking.</p>
          </section>
        );
      })}
    </>
  );
}

export default function ReadinessPage() {
  return (
    <RoleGate roles={["sme"]}>
      <Suspense fallback={<p>Loading readiness…</p>}>
        <ReadinessView />
      </Suspense>
    </RoleGate>
  );
}
