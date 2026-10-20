"use client";

import { ArrowDownLeft, ArrowRight, Crosshair, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId } from "react";
import { Eyebrow } from "@/components/Eyebrow";
import { SectionIndex } from "@/components/SectionIndex";
import { ROLE_HOME, useIdentity } from "@/lib/identity";
import type { Role } from "@/lib/types";

const ROLES: { role: Role; title: string; description: string }[] = [
  { role: "sme", title: "SME", description: "Upload documents, confirm AI-extracted facts, control sharing." },
  { role: "buyer", title: "Buyer", description: "Structure an RFQ, run rule-based matching, shortlist with evidence." },
  { role: "admin", title: "YES Admin", description: "See pipeline outcomes, readiness gaps and fairness." },
];

/** Decorative grayscale noise texture (local SVG filter, no remote image). */
function HeroGraphic() {
  const filterId = useId().replace(/:/g, "");
  return (
    <div className="hero-graphic" aria-hidden="true">
      <div className="hero-graphic-art" />
      <svg xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">
        <filter id={filterId}>
          <feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="3" stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="100%" height="100%" filter={`url(#${filterId})`} />
      </svg>
      <div className="hero-graphic-fade" />
    </div>
  );
}

/** Rotating circular stamp (decorative; the spin is disabled under prefers-reduced-motion). */
function Stamp() {
  const pathId = useId().replace(/:/g, "");
  return (
    <div className="stamp" aria-hidden="true">
      <svg viewBox="0 0 100 100" className="stamp-ring">
        <path id={pathId} d="M 50, 50 m -35, 0 a 35,35 0 1,1 70,0 a 35,35 0 1,1 -70,0" fill="none" />
        <text>
          <textPath href={`#${pathId}`} startOffset="0%">
            Explainable matching • Explainable matching •{" "}
          </textPath>
        </text>
      </svg>
      <Crosshair size={32} strokeWidth={1.5} />
    </div>
  );
}

/** Landing page: hero plus one numbered entry per demo role. */
export default function Home() {
  const { identities, identity, setIdentity } = useIdentity();
  const router = useRouter();
  const loaded = identities.length > 0;

  function enter(role: Role) {
    let slug: string | null = null;
    if (role === "sme") {
      const firstSme = identities.find((i) => i.role === "sme");
      slug = identity?.role === "sme" && identity.sme_slug ? identity.sme_slug : (firstSme?.sme_slug ?? null);
    }
    setIdentity(role, slug);
    router.push(ROLE_HOME[role]);
  }

  return (
    <>
      <section className="hero full-bleed" aria-labelledby="hero-heading">
        <HeroGraphic />
        <div className="container">
          <div className="hero-content">
            <Eyebrow label="Procurement matching · Fictional demo" />
            <h1 id="hero-heading" className="display">
              Match.
              <br />
              Prove.
              <br />
              Shortlist.
            </h1>
            <p className="lead">
              Evidenced, explainable shortlists that connect youth-owned IT SMEs with buyers. Rules decide eligibility; a
              human makes every decision.
            </p>
            <div className="hero-links">
              <a href="#roles" className="link-arrow">
                Choose a demo role
                <ArrowRight size={16} strokeWidth={1.5} aria-hidden="true" />
              </a>
              {identity && loaded ? (
                <Link href={ROLE_HOME[identity.role]} className="link-arrow">
                  Continue as {identity.label}
                  <ArrowRight size={16} strokeWidth={1.5} aria-hidden="true" />
                </Link>
              ) : null}
            </div>
          </div>
        </div>
        <div className="accent-square" aria-hidden="true">
          <ArrowDownLeft size={40} strokeWidth={1.5} />
        </div>
        <Stamp />
      </section>

      <section id="roles" className="landing-section alt full-bleed" aria-labelledby="roles-heading">
        <div className="container">
          <SectionIndex n={1} label="Demo roles" />
          <h2 id="roles-heading">Three users, one platform</h2>
          <ul className="row-list role-rows">
            {ROLES.map((r, i) => (
              <li className="row" key={r.role}>
                <button type="button" className="row-button" disabled={!loaded} onClick={() => enter(r.role)}>
                  <span className="row-index" aria-hidden="true">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span>
                    <span className="sr-only">Enter as </span>
                    <span className="role-title">{r.title}</span>
                    <span className="sr-only">: </span>
                    <span className="role-desc">{loaded ? r.description : "Loading roles…"}</span>
                  </span>
                  <span className="btn-circle" aria-hidden="true">
                    <Plus size={24} strokeWidth={1.5} />
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="manifesto full-bleed" aria-label="Principle">
        <h2>
          Rules decide eligibility.
          <br />
          <span className="on-accent-light">AI explains. Humans decide.</span>
        </h2>
      </section>
    </>
  );
}
