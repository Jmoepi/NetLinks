"use client";

import Link from "next/link";
import { Notice } from "@/components/Notice";
import { RoleGate } from "@/components/RoleGate";
import { formatDateTime } from "@/lib/format";
import { useLoad } from "@/lib/useLoad";
import type { OpportunitySummary } from "@/lib/types";

function OpportunityList() {
  const { data, error, loading } = useLoad<OpportunitySummary[]>("/api/opportunities");
  if (!data) return loading ? <p>Loading opportunities…</p> : <Notice kind="error">{error}</Notice>;

  return (
    <>
      <h1>Your opportunities</h1>
      <p className="muted">Ubuntu Office Parks (fictional) · Buyer: Naledi</p>
      {data.map((o) => (
        <section className="panel" key={o.id} aria-labelledby={`opp-${o.id}`}>
          <h2 id={`opp-${o.id}`}>{o.title}</h2>
          <p className="muted">
            {o.buyer_org} · status {o.status} · closes {o.closing_date} · contract starts {o.contract_start}
          </p>
          <p>
            {o.latest_run
              ? `Last matching run ${formatDateTime(o.latest_run.run_at)}: Eligible ${o.latest_run.counts.eligible}, Needs Review ${o.latest_run.counts.needs_review}, Not Eligible ${o.latest_run.counts.not_eligible}.`
              : "Matching has not been run yet."}
          </p>
          <div className="button-row">
            <Link href={`/buyer/opportunities/${o.id}`}>Requirements and weights</Link>
            <span aria-hidden="true">·</span>
            <Link href={`/buyer/opportunities/${o.id}/results`}>Matching results and shortlist</Link>
            <span aria-hidden="true">·</span>
            <Link href={`/buyer/audit?opportunity_id=${o.id}`}>Audit log</Link>
          </div>
        </section>
      ))}
    </>
  );
}

export default function BuyerPage() {
  return (
    <RoleGate roles={["buyer"]}>
      <OpportunityList />
    </RoleGate>
  );
}
