"use client";

// Account menu for the simulated sign-in: shows the persona and role, lets the presenter switch account (demo)
// and sign out. Disclosure pattern (button + panel), not an ARIA menu: Escape closes and returns focus to the
// trigger, and the panel also closes on outside click and on route change.

import { Check, ChevronDown, User } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { keyOf, ROLE_HOME, useIdentity } from "@/lib/identity";
import { demoEmail, personaLabel, ROLE_NAMES } from "@/lib/personas";
import type { Identity } from "@/lib/types";
import { belongsTo } from "./nav";

export function AccountMenu() {
  const { identities, identity, identityKey, setIdentity, signOut } = useIdentity();
  const router = useRouter();
  const pathname = usePathname();
  const panelId = useId();
  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const wrapper = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const lastPath = useRef(pathname);

  // Close when the route changes.
  useEffect(() => {
    if (pathname !== lastPath.current) {
      lastPath.current = pathname;
      setOpen(false);
    }
  }, [pathname]);

  // Opening moves focus to the first persona button; a mousedown outside closes the panel.
  useEffect(() => {
    if (!open) return;
    wrapper.current?.querySelector<HTMLButtonElement>(".account-option")?.focus();
    function onMouseDown(e: MouseEvent) {
      if (wrapper.current && !wrapper.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, [open]);

  // Sign out only once the landing page is reached; signing out on a gated screen would make its RoleGate
  // redirect to /login before the navigation to / commits.
  useEffect(() => {
    if (signingOut && pathname === "/") signOut();
  }, [signingOut, pathname, signOut]);

  if (!identity) return null;
  const name = identity.name || identity.label;

  function close(refocus: boolean) {
    setOpen(false);
    if (refocus) trigger.current?.focus();
  }

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === "Escape" && open) {
      e.preventDefault();
      close(true);
    }
  }

  function switchTo(i: Identity) {
    setIdentity(i.role, i.sme_slug);
    if (!belongsTo(i.role, pathname)) router.push(ROLE_HOME[i.role]);
    close(true);
  }

  function onSignOut() {
    setOpen(false);
    setSigningOut(true);
    if (pathname !== "/") router.push("/");
  }

  return (
    <div className="account-menu" ref={wrapper} onKeyDown={onKeyDown}>
      <button
        ref={trigger}
        type="button"
        className="account-trigger"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={`Account: ${name}, ${ROLE_NAMES[identity.role]}`}
        onClick={() => setOpen((v) => !v)}
      >
        <User size={16} strokeWidth={1.5} aria-hidden="true" />
        <span className="account-trigger-name">{name}</span>
        <span className="pill">{ROLE_NAMES[identity.role]}</span>
        <ChevronDown size={14} strokeWidth={1.5} aria-hidden="true" className="account-chevron" />
      </button>
      <div id={panelId} className="account-panel" hidden={!open}>
        <p className="account-name">{name}</p>
        <p className="account-meta">
          {ROLE_NAMES[identity.role]} · <span className="mono">{demoEmail(identity)}</span>
        </p>
        <h2 className="account-heading">Switch account (demo)</h2>
        <ul className="account-list">
          {identities.map((i) => {
            const key = keyOf(i.role, i.sme_slug);
            const current = key === identityKey;
            return (
              <li key={key}>
                <button
                  type="button"
                  className="account-option"
                  aria-current={current ? "true" : undefined}
                  onClick={() => switchTo(i)}
                >
                  {personaLabel(i)}
                  {current ? <Check size={14} strokeWidth={1.5} aria-hidden="true" /> : null}
                </button>
              </li>
            );
          })}
        </ul>
        <button type="button" className="secondary account-signout" onClick={onSignOut}>
          Sign out
        </button>
      </div>
    </div>
  );
}
