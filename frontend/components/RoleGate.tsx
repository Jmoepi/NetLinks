"use client";

import type { ReactNode } from "react";
import { useIdentity } from "@/lib/identity";
import type { Role } from "@/lib/types";
import { Eyebrow } from "./Eyebrow";

const ROLE_NAMES: Record<Role, string> = { sme: "an SME", buyer: "the Buyer", admin: "YES Admin" };

/**
 * Hides a screen that does not belong to the selected demo role. This is only a UI convenience:
 * the API enforces the same permissions server-side.
 */
export function RoleGate({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { ready, identity } = useIdentity();
  if (!ready || !identity) return <p>Loading…</p>;
  if (!roles.includes(identity.role)) {
    return (
      <section className="panel">
        <Eyebrow label="Demo role" />
        <h1>Switch role to continue</h1>
        <p>
          This screen is for {roles.map((r) => ROLE_NAMES[r]).join(" or ")}. Choose that role with the
          &quot;Demo role&quot; selector in the top bar.
        </p>
      </section>
    );
  }
  return <>{children}</>;
}
