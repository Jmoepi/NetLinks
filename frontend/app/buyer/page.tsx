"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Suspense, useEffect } from "react";
import { Eyebrow } from "@/components/Eyebrow";
import { Notice } from "@/components/Notice";
import { Pagination } from "@/components/Pagination";
import { RoleGate } from "@/components/RoleGate";
import { formatDateTime } from "@/lib/format";
import { usePageParam } from "@/lib/pagination";
import { useLoad } from "@/lib/useLoad";
import type { OpportunitySummary, Paginated } from "@/lib/types";

const PAGE_SIZE = 10;

function OpportunityList() {
  const router = useRouter();
  const { page, setPage, hrefFor } = usePageParam("page");
  const { data, error, loading } = useLoad<Paginated<OpportunitySummary>>(
    `/api/opportunities?page=${page}&page_size=${PAGE_SIZE}`,
  );

  // A page past the end (e.g. a stale or edited URL) jumps to the last page instead of showing an empty list.
  useEffect(() => {
    if (data && data.items.length === 0 && data.total > 0 && data.page > 1) {
      router.replace(hrefFor(Math.ceil(data.total / data.page_size)), { scroll: false });
    }
  }, [data, hrefFor, router]);

  if (!data) return loading ? <p>Loading opportunities…</p> : <Notice kind="error">{error}</Notice>;
  const offset = (data.page - 1) * data.page_size;

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
      {data.items.map((o, i) => (
        <section className="row" key={o.id} aria-labelledby={`opp-${o.id}`}>
          <div className="row-inner">
          <span className="row-index" aria-hidden="true">
            {String(offset + i + 1).padStart(2, "0")}
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
      <Pagination
        label="Opportunities"
        page={data.page}
        pageSize={data.page_size}
        total={data.total}
        onPageChange={setPage}
      />
    </>
  );
}

export default function BuyerPage() {
  return (
    <RoleGate roles={["buyer"]}>
      <Suspense fallback={<p>Loading opportunities…</p>}>
        <OpportunityList />
      </Suspense>
    </RoleGate>
  );
}
