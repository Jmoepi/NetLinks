"use client";

import { Crosshair, Database, Menu } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useId, useRef, useState, type ChangeEvent } from "react";
import { keyOf, ROLE_HOME, useIdentity } from "@/lib/identity";
import { MobileMenu } from "./MobileMenu";
import { belongsTo, NAV } from "./nav";

export function TopBar() {
  const { identities, identity, identityKey, setIdentity, aiMode, loadError } = useIdentity();
  const router = useRouter();
  const pathname = usePathname();
  const selectId = useId();
  const menuId = useId();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const closeMenu = useCallback(() => setMenuOpen(false), []);

  function onChange(e: ChangeEvent<HTMLSelectElement>) {
    const next = identities.find((i) => keyOf(i.role, i.sme_slug) === e.target.value);
    if (!next) return;
    setIdentity(next.role, next.sme_slug);
    if (!belongsTo(next.role, pathname)) router.push(ROLE_HOME[next.role]);
  }

  const smes = identities.filter((i) => i.role === "sme");
  const others = identities.filter((i) => i.role !== "sme");
  const live = aiMode?.mode === "live";
  const links = identity ? NAV[identity.role] : [];

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner container">
          <Link href="/" className="brand" aria-label="NetLinks home">
            <Crosshair size={20} strokeWidth={1.5} aria-hidden="true" />
            <span aria-hidden="true">
              Net <span className="accent">/</span> Links
            </span>
          </Link>
          <nav aria-label="Main" className="nav-desktop">
            <ul className="nav-list">
              {links.map((item) => (
                <li key={item.href}>
                  <Link href={item.href} aria-current={pathname === item.href ? "page" : undefined}>
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <button
            ref={menuButton}
            type="button"
            className="icon-button menu-button"
            aria-label="Open menu"
            aria-expanded={menuOpen}
            aria-controls={menuId}
            onClick={() => setMenuOpen(true)}
          >
            <Menu size={24} strokeWidth={1.5} aria-hidden="true" />
          </button>
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
              {live ? (
                <span className="live-dot" aria-hidden="true" />
              ) : (
                <Database size={14} strokeWidth={1.5} aria-hidden="true" />
              )}
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
      <MobileMenu id={menuId} open={menuOpen} onClose={closeMenu} links={links} triggerRef={menuButton} />
    </>
  );
}
