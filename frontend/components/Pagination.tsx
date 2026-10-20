"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

/** Page numbers to show: all when 7 or fewer, else first, last and current ±1 with gaps marked as null. */
function pageItems(page: number, totalPages: number): (number | null)[] {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);
  const keep = new Set([1, totalPages, page - 1, page, page + 1]);
  const items: (number | null)[] = [];
  for (let n = 1; n <= totalPages; n++) {
    if (!keep.has(n)) continue;
    const prev = items[items.length - 1];
    if (typeof prev === "number" && n - prev > 1) items.push(null);
    items.push(n);
  }
  return items;
}

/**
 * Shared list pagination. Hidden when everything fits on one page.
 * Previous/Next use aria-disabled (not disabled) at the ends so they stay focusable and announced.
 */
export function Pagination({
  label,
  page,
  pageSize,
  total,
  onPageChange,
}: {
  label: string;
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (p: number) => void;
}) {
  if (total <= pageSize) return null;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const current = Math.min(Math.max(1, page), totalPages);
  const from = (current - 1) * pageSize + 1;
  const to = Math.min(current * pageSize, total);
  const atStart = current <= 1;
  const atEnd = current >= totalPages;

  return (
    <nav aria-label={`${label} pagination`} className="pagination">
      <p role="status" className="pagination-status">
        Showing {from}–{to} of {total}
      </p>
      <ul>
        <li>
          <button
            type="button"
            className="pagination-step"
            aria-disabled={atStart ? "true" : undefined}
            onClick={() => {
              if (!atStart) onPageChange(current - 1);
            }}
          >
            <ChevronLeft size={14} strokeWidth={1.5} aria-hidden="true" />
            Previous
          </button>
        </li>
        {pageItems(current, totalPages).map((n, i) =>
          n === null ? (
            <li key={`gap-${i}`}>
              <span className="pagination-gap" aria-hidden="true">
                …
              </span>
            </li>
          ) : (
            <li key={n}>
              <button
                type="button"
                className="pagination-page"
                aria-label={`Page ${n}`}
                aria-current={n === current ? "page" : undefined}
                onClick={() => {
                  if (n !== current) onPageChange(n);
                }}
              >
                {n}
              </button>
            </li>
          ),
        )}
        <li>
          <button
            type="button"
            className="pagination-step"
            aria-disabled={atEnd ? "true" : undefined}
            onClick={() => {
              if (!atEnd) onPageChange(current + 1);
            }}
          >
            Next
            <ChevronRight size={14} strokeWidth={1.5} aria-hidden="true" />
          </button>
        </li>
      </ul>
    </nav>
  );
}
