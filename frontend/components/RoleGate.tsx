"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { ROLE_HOME, useIdentity } from "@/lib/identity";
import { personaLabel, ROLE_NAMES } from "@/lib/personas";
import type { Role } from "@/lib/types";
import { Eyebrow } from "./Eyebrow";

/** Current path plus query, for the sign-in `next` parameter (window.location avoids a Suspense boundary). */
function currentPath(fallback: string): string {
  return typeof window === "undefined" ? fallback : window.location.pathname + window.location.search;
}

/**
 * Sends signed-out visitors to the simulated sign-in and hides a screen that does not belong to the signed-in
 * role. This is only a UI convenience: the API enforces the same permissions server-side.
 */
export function RoleGate({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { ready, signedIn, identity } = useIdentity();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (ready && !signedIn) router.replace(`/login?next=${encodeURIComponent(currentPath(pathname))}`);
  }, [ready, signedIn, router, pathname]);

  if (!ready) return <p>Loading…</p>;
  if (!signedIn || !identity) {
    return (
      <p>
        Redirecting to sign in… <Link href="/login">Sign in</Link>
      </p>
    );
  }
  if (!roles.includes(identity.role)) {
    return (
      <section className="panel">
        <Eyebrow label="Access denied" />
        <h1>Access denied for this role</h1>
        <p>
          This screen is for {roles.map((r) => ROLE_NAMES[r]).join(" or ")}. You are signed in as{" "}
          {personaLabel(identity)}.
        </p>
        <div className="link-row">
          <Link href={`/login?next=${encodeURIComponent(currentPath(pathname))}`} className="link-arrow">
            Switch account
            <ArrowRight size={16} strokeWidth={1.5} aria-hidden="true" />
          </Link>
          <Link href={ROLE_HOME[identity.role]} className="link-arrow">
            Go to your home
            <ArrowRight size={16} strokeWidth={1.5} aria-hidden="true" />
          </Link>
        </div>
      </section>
    );
  }
  return <>{children}</>;
}
