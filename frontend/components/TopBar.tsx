"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useId, type ChangeEvent } from "react";
import { keyOf, ROLE_HOME, useIdentity } from "@/lib/identity";
import type { Role } from "@/lib/types";

const NAV: Record<Role, { href: string; label: string }[]> = {
  sme: [
    { href: "/sme", label: "My profile" },
    { href: "/sme/readiness", label: "Readiness" },
  ],
  buyer: [
    { href: "/buyer", label: "Opportunities" },
    { href: "/buyer/audit", label: "Audit log" },
  ],
  admin: [
    { href: "/admin", label: "YES dashboard" },
    { href: "/buyer/audit", label: "Audit log" },
  ],
};

function belongsTo(role: Role, pathname: string): boolean {
  if (pathname.startsWith("/documents")) return true;
  return pathname === ROLE_HOME[role] || pathname.startsWith(`${ROLE_HOME[role]}/`);
}

export function TopBar() {
  const { identities, identity, identityKey, setIdentity, aiMode, loadError } = useIdentity();
  const router = useRouter();
  const pathname = usePathname();
  const selectId = useId();

  function onChange(e: ChangeEvent<HTMLSelectElement>) {
    const next = identities.find((i) => keyOf(i.role, i.sme_slug) === e.target.value);
    if (!next) return;
    setIdentity(next.role, next.sme_slug);
    if (!belongsTo(next.role, pathname)) router.push(ROLE_HOME[next.role]);
  }

  const smes = identities.filter((i) => i.role === "sme");
  const others = identities.filter((i) => i.role !== "sme");
  const live = aiMode?.mode === "live";

  return (
    <header className="topbar">
      <div className="topbar-inner">
        <Link href="/" className="brand">
          NetLinks
        </Link>
        <nav aria-label="Main">
          <ul className="nav-list">
            {identity
              ? NAV[identity.role].map((item) => (
                  <li key={item.href}>
                    <Link href={item.href} aria-current={pathname === item.href ? "page" : undefined}>
                      {item.label}
                    </Link>
                  </li>
                ))
              : null}
          </ul>
        </nav>
        <div className="topbar-controls">
          <div className="role-switcher">
            <label htmlFor={selectId}>Demo role (demo simplification; production uses Cognito)</label>
            <select id={selectId} value={identityKey} onChange={onChange} disabled={!identities.length}>
              {!identities.length && identityKey ? <option value={identityKey}>Loading roles…</option> : null}
              <optgroup label="SME">
                {smes.map((i) => (
                  <option key={keyOf(i.role, i.sme_slug)} value={keyOf(i.role, i.sme_slug)}>
                    SME - {i.name}
                  </option>
                ))}
              </optgroup>
              <optgroup label="Buyer and YES">
                {others.map((i) => (
                  <option key={keyOf(i.role, i.sme_slug)} value={keyOf(i.role, i.sme_slug)}>
                    {i.role === "buyer" ? `Buyer - ${i.name} (Ubuntu Office Parks)` : i.label}
                  </option>
                ))}
              </optgroup>
            </select>
          </div>
          <span
            className={`badge ${live ? "badge-live" : "badge-cached"}`}
            title={
              live
                ? "Live: documents are processed by Amazon Bedrock now."
                : "Cached: AI results were generated earlier by the pipeline from these exact documents."
            }
          >
            <span aria-hidden="true" className="badge-icon">
              {live ? "●" : "◆"}
            </span>
            {aiMode ? `AI mode: ${live ? "Live" : "Cached"}` : "AI mode: unknown"}
          </span>
        </div>
      </div>
      {loadError ? (
        <p className="notice notice-error" role="alert">
          {loadError}
        </p>
      ) : null}
    </header>
  );
}
