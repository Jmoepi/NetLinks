"use client";

// Simulated sign-in: pick a role and a fictional persona. No real authentication: the demo email and the
// "demo" password are display-only and are never sent to the API or stored. Production uses Amazon Cognito.

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useId, useState, type FormEvent } from "react";
import { Eyebrow } from "@/components/Eyebrow";
import { canAccess } from "@/components/nav";
import { Notice } from "@/components/Notice";
import { ROLE_HOME, useIdentity } from "@/lib/identity";
import { demoEmail, personaLabel, personaName } from "@/lib/personas";
import type { Role } from "@/lib/types";

const ROLES: { role: Role; title: string; description: string }[] = [
  { role: "sme", title: "SME", description: "Upload documents, confirm AI-extracted facts, control sharing." },
  { role: "buyer", title: "Buyer", description: "Structure an RFQ, run rule-based matching, shortlist with evidence." },
  { role: "admin", title: "YES Admin", description: "See pipeline outcomes, readiness gaps and fairness." },
];

/** Returns `next` when it is a same-site path the role may open, otherwise null (prevents open redirects). */
function safeNext(next: string | null, role: Role): string | null {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\") || next.startsWith("/login")) {
    return null;
  }
  return canAccess(role, next.split(/[?#]/)[0]) ? next : null;
}

function LoginForm() {
  const { identities, identity, signedIn, setIdentity, loadError } = useIdentity();
  const router = useRouter();
  const next = useSearchParams().get("next");
  const uid = useId();
  const [role, setRole] = useState<Role>(identity?.role ?? "sme");
  const [smeSlug, setSmeSlug] = useState<string | null>(identity?.role === "sme" ? identity.sme_slug : null);

  const personas = identities.filter((i) => i.role === role);
  const persona =
    role === "sme" ? (personas.find((i) => i.sme_slug === smeSlug) ?? personas[0] ?? null) : (personas[0] ?? null);

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!persona) return;
    setIdentity(persona.role, persona.sme_slug);
    router.replace(safeNext(next, persona.role) ?? ROLE_HOME[persona.role]);
  }

  return (
    <>
      <div className="page-header">
        <div>
          <Eyebrow label="Demo sign-in" />
          <h1>Sign in</h1>
        </div>
      </div>
      <Notice kind="info">Simulated sign-in for the demo. No real authentication. Production uses Amazon Cognito.</Notice>
      {loadError ? <Notice kind="error">{loadError}</Notice> : null}
      {signedIn && identity ? (
        <div className="link-row signed-in-row">
          <p>Signed in as {personaLabel(identity)}</p>
          <Link href={safeNext(next, identity.role) ?? ROLE_HOME[identity.role]} className="link-arrow">
            Continue
            <ArrowRight size={16} strokeWidth={1.5} aria-hidden="true" />
          </Link>
        </div>
      ) : null}

      <form className="login-grid" onSubmit={onSubmit}>
        <div>
          <fieldset>
            <legend>1. Choose a role</legend>
            <ul className="choice-list">
              {ROLES.map((r, i) => (
                <li key={r.role}>
                  <label className="choice">
                    <span className="row-index" aria-hidden="true">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <input
                      type="radio"
                      name="role"
                      value={r.role}
                      checked={role === r.role}
                      onChange={() => setRole(r.role)}
                    />
                    <span className="choice-text">
                      <span className="choice-title">{r.title}</span>
                      <span className="choice-desc">{r.description}</span>
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          </fieldset>
          <fieldset>
            <legend>2. Choose a persona</legend>
            {personas.length ? (
              <ul className="choice-list">
                {personas.map((p, i) => (
                  <li key={`${p.role}:${p.sme_slug ?? ""}`}>
                    <label className="choice">
                      <span className="row-index" aria-hidden="true">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <input
                        type="radio"
                        name="persona"
                        value={p.sme_slug ?? p.role}
                        checked={persona === p}
                        onChange={() => setSmeSlug(p.sme_slug)}
                      />
                      <span className="choice-text">
                        <span className="choice-title">{personaName(p)}</span>
                        <span className="choice-desc mono">{demoEmail(p)}</span>
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="hint">{loadError ? "Personas could not be loaded." : "Loading personas…"}</p>
            )}
          </fieldset>
        </div>
        <fieldset className="login-credentials">
          <legend>3. Demo credentials</legend>
          <div className="field">
            <label htmlFor={`${uid}-email`}>Demo email</label>
            <input id={`${uid}-email`} type="email" value={persona ? demoEmail(persona) : ""} readOnly />
          </div>
          <div className="field">
            <label htmlFor={`${uid}-password`}>Password (demo)</label>
            <input
              id={`${uid}-password`}
              type="password"
              value="demo"
              readOnly
              autoComplete="off"
              aria-describedby={`${uid}-password-hint`}
            />
            <p id={`${uid}-password-hint`} className="hint">
              Not checked or stored. Any persona can sign in.
            </p>
          </div>
          <button type="submit" disabled={!identities.length || !persona}>
            Sign in
          </button>
        </fieldset>
      </form>
    </>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<p>Loading…</p>}>
      <LoginForm />
    </Suspense>
  );
}
