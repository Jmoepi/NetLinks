"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { Eyebrow } from "@/components/Eyebrow";
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
      <div className="page-header">
        <div>
          <Eyebrow label="Buyer workspace" />
          <h1>Your opportunities</h1>
          <p className="meta">Ubuntu Office Parks (fictional) · Buyer: Naledi</p>
        </div>
      </div>
      <div className="row-list">
      {data.map((o, i) => (
        <section className="row" key={o.id} aria-labelledby={`opp-${o.id}`}>
          <div className="row-inner">
          <span className="row-index" aria-hidden="true">
            {String(i + 1).padStart(2, "0")}
          </span>
          <div className="row-body">
          <h2 id={`opp-${o.id}`} className="row-title-lg">{o.title}</h2>
          <p className="meta">
            {o.buyer_org} · status {o.status} · closes {o.closing_date} · contract starts {o.contract_start}
          </p>
          <p>
            {o.latest_run
              ? `Last matching run ${formatDateTime(o.latest_run.run_at)}: Eligible ${o.latest_run.counts.eligible}, Needs Review ${o.latest_run.counts.needs_review}, Not Eligible ${o.latest_run.counts.not_eligible}.`
              : "Matching has not been run yet."}
          </p>
          <div className="link-row">
            <Link href={`/buyer/opportunities/${o.id}`} className="link-arrow">
              Requirements and weights
              <ArrowRight size={16} strokeWidth={1.5} aria-hidden="true" />
            </Link>
            <Link href={`/buyer/opportunities/${o.id}/results`} className="link-arrow">
              Matching results and shortlist
              <ArrowRight size={16} strokeWidth={1.5} aria-hidden="true" />
            </Link>
            <Link href={`/buyer/audit?opportunity_id=${o.id}`} className="link-arrow">
              Audit log
              <ArrowRight size={16} strokeWidth={1.5} aria-hidden="true" />
            </Link>
          </div>
          </div>
          </div>
        </section>
      ))}
      </div>
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
