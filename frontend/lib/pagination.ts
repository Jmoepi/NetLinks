"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

/** Parse a 1-based page number from a query value; anything else means page 1. */
function parsePage(value: string | null): number {
  if (!value || !/^\d+$/.test(value)) return 1;
  const n = Number(value);
  return n >= 1 ? n : 1;
}

/**
 * Page state kept in the URL query (?{name}=N), so refresh and browser Back work.
 * Page 1 drops the key to keep URLs clean. Callers must render inside <Suspense> (useSearchParams).
 */
export function usePageParam(name = "page") {
  const search = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const page = parsePage(search.get(name));

  const hrefFor = useCallback(
    (n: number) => {
      const params = new URLSearchParams(search.toString());
      if (n <= 1) params.delete(name);
      else params.set(name, String(n));
      const qs = params.toString();
      return `${pathname}${qs ? `?${qs}` : ""}`;
    },
    [name, pathname, search],
  );

  const setPage = useCallback((n: number) => router.push(hrefFor(n), { scroll: false }), [hrefFor, router]);

  return { page, setPage, hrefFor };
}

/** Client-side slice of a fully loaded list; out-of-range pages are clamped to [1, totalPages]. */
export function pageSlice<T>(items: T[], page: number, size: number) {
  const totalPages = Math.max(1, Math.ceil(items.length / size));
  const current = Math.min(Math.max(1, page), totalPages);
  const offset = (current - 1) * size;
  return { items: items.slice(offset, offset + size), page: current, totalPages, offset };
}
