"use client";

import { ArrowRight, Crosshair, Database, Menu } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useId, useRef, useState } from "react";
import { useIdentity } from "@/lib/identity";
import { AccountMenu } from "./AccountMenu";
import { MobileMenu } from "./MobileMenu";
import { NAV } from "./nav";

export function TopBar() {
  const { identity, signedIn, aiMode, loadError } = useIdentity();
  const pathname = usePathname();
  const menuId = useId();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const closeMenu = useCallback(() => setMenuOpen(false), []);

  const live = aiMode?.mode === "live";
  const links = signedIn && identity ? NAV[identity.role] : [];

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
            {signedIn ? (
              <>
                <AccountMenu />
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
              </>
            ) : pathname !== "/login" ? (
              <Link href="/login" className="link-arrow">
                Sign in
                <ArrowRight size={16} strokeWidth={1.5} aria-hidden="true" />
              </Link>
            ) : null}
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
