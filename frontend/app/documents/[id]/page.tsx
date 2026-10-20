"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Suspense, useEffect, useRef } from "react";
import { Eyebrow } from "@/components/Eyebrow";
import { Notice } from "@/components/Notice";
import { SectionIndex } from "@/components/SectionIndex";
import { docTypeLabel } from "@/lib/format";
import { useLoad } from "@/lib/useLoad";
import type { DocumentText } from "@/lib/types";

function intParam(value: string | null): number | null {
  if (value === null) return null;
  const n = Number(value);
  return Number.isInteger(n) && n >= 0 ? n : null;
}

function Viewer() {
  const params = useParams<{ id: string }>();
  const search = useSearchParams();
  const router = useRouter();
  const { data, error, loading } = useLoad<DocumentText>(`/api/documents/${encodeURIComponent(params.id)}/text`);
  const markRef = useRef<HTMLElement>(null);

  const page = intParam(search.get("page")) ?? 1;
  const start = intParam(search.get("start"));
  const end = intParam(search.get("end"));

  useEffect(() => {
    if (data && markRef.current) {
      markRef.current.scrollIntoView({ block: "center" });
      markRef.current.focus();
    }
  }, [data]);

  if (!data) return loading ? <p>Loading document…</p> : <Notice kind="error">{error}</Notice>;

  return (
    <>
      <div className="page-header">
        <div>
          <Eyebrow label="Source document" />
          <h1>{data.filename}</h1>
          <p className="meta">
            {docTypeLabel(data.doc_type)} · {data.sme_name} · {data.page_count} page{data.page_count === 1 ? "" : "s"}
            {data.period_end ? ` · valid to ${data.period_end}` : ""}
          </p>
        </div>
        <button type="button" className="secondary" onClick={() => router.back()}>
          <ArrowLeft size={14} strokeWidth={1.5} aria-hidden="true" />
          Back
        </button>
      </div>
      {start !== null && end !== null ? (
        <Notice kind="info">The highlighted text on page {page} is the source of the selected value.</Notice>
      ) : null}
      {data.pages.map((text, i) => {
        const pageNo = i + 1;
        const highlight = pageNo === page && start !== null && end !== null && end > start && end <= text.length;
        return (
          <section key={pageNo} aria-label={`Page ${pageNo}`}>
            <SectionIndex n={pageNo} label="Page" />
            <h2>Page {pageNo}</h2>
            <div className="doc-page">
              {highlight ? (
                <>
                  {text.slice(0, start!)}
                  <mark ref={markRef} tabIndex={-1}>
                    {text.slice(start!, end!)}
                  </mark>
                  {text.slice(end!)}
                </>
              ) : (
                text
              )}
            </div>
          </section>
        );
      })}
    </>
  );
}

export default function DocumentPage() {
  return (
    <Suspense fallback={<p>Loading document…</p>}>
      <Viewer />
    </Suspense>
  );
}
