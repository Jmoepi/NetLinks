"use client";

import { ArrowDownLeft, ArrowRight, Crosshair } from "lucide-react";
import Link from "next/link";
import { useId } from "react";
import { Eyebrow } from "@/components/Eyebrow";
import { SectionIndex } from "@/components/SectionIndex";
import { ROLE_HOME, useIdentity } from "@/lib/identity";

/** Static landing content. Plain statements only: no metrics, logos, testimonials or partner claims. */
const PROBLEMS = [
  "SMEs struggle to present their capabilities in a form buyers can assess.",
  "Buyers spend hours screening documents.",
];

const STEPS: { title: string; text: string }[] = [
  { title: "Structured SME profiles", text: "AI-assisted extraction from documents, which the SME confirms." },
  {
    title: "Structured opportunity requirements",
    text: "Buyers turn a request into mandatory requirements and weighted criteria.",
  },
  { title: "Deterministic mandatory eligibility", text: "Eligible / Needs Review / Not Eligible." },
  {
    title: "Transparent fit scoring",
    text: "40% capability, 25% experience, 20% capacity, 15% location, with semantic matching.",
  },
  {
    title: "Explainable shortlists",
    text: "Evidence, gaps and readiness actions for every match, plus an audit trail.",
  },
];

const AUDIENCES: { title: string; text: string }[] = [
  { title: "SMEs", text: "Build one evidenced profile and see what would help you qualify." },
  {
    title: "Corporate buyers and ESD teams",
    text: "Structure a request, apply mandatory rules and shortlist with evidence behind every score.",
  },
  {
    title: "YES and ecosystem partners",
    text: "See pipeline outcomes, common readiness gaps and fairness across matches.",
  },
];

const TRUST = [
  "POPIA-aligned",
  "SME consent before buyers see a profile",
  "Role-based access enforced server-side",
  "Data in AWS Cape Town (af-south-1) in production",
];

const ROADMAP = [
  "Funding and grant matching",
  "Buyer feedback with an SME right of reply",
  "Procurement portal integrations",
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

function index(i: number): string {
  return String(i + 1).padStart(2, "0");
}

/** Numbered row with an optional title above the text (shared by the landing sections). */
function LandingRow({ i, title, text }: { i: number; title?: string; text?: string }) {
  return (
    <li className="row">
      <div className="row-inner">
        <span className="row-index" aria-hidden="true">
          {index(i)}
        </span>
        <div className="row-body">
          {title ? <h3 className="row-title">{title}</h3> : null}
          {text ? <p className={title ? "muted" : "landing-statement"}>{text}</p> : null}
        </div>
      </div>
    </li>
  );
}

/** Public landing page: hero, numbered content sections and a sign-in call to action. */
export default function Home() {
  const { identities, identity, signedIn } = useIdentity();
  const loaded = identities.length > 0;

  return (
    <>
      <section className="hero full-bleed" aria-labelledby="hero-heading">
        <HeroGraphic />
        <div className="container">
          <div className="hero-content">
            <Eyebrow label="Supplier readiness · Fictional demo" />
            <h1 id="hero-heading" className="display">
              Match.
              <br />
              Prove.
              <br />
              Shortlist.
            </h1>
            <p className="lead">
              NetLinks is an explainable supplier-readiness and opportunity-intelligence platform connecting youth-owned
              SMEs with corporate procurement.
            </p>
            <div className="hero-links">
              <Link href="/login" className="button-link">
                Sign in to the demo
                <ArrowRight size={16} strokeWidth={1.5} aria-hidden="true" />
              </Link>
              <a href="#how" className="link-arrow">
                How it works
                <ArrowRight size={16} strokeWidth={1.5} aria-hidden="true" />
              </a>
              {signedIn && identity && loaded ? (
                <Link href={ROLE_HOME[identity.role]} className="link-arrow">
                  Continue as {identity.name || identity.label}
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

      <section className="landing-section alt full-bleed" aria-labelledby="problem-heading">
        <div className="container">
          <SectionIndex n={1} label="Problem" />
          <h2 id="problem-heading">The problem</h2>
          <ol className="row-list">
            {PROBLEMS.map((text, i) => (
              <LandingRow key={text} i={i} text={text} />
            ))}
          </ol>
        </div>
      </section>

      <section id="how" className="landing-section full-bleed" aria-labelledby="how-heading">
        <div className="container">
          <SectionIndex n={2} label="How it works" />
          <h2 id="how-heading">How it works</h2>
          <ol className="row-list">
            {STEPS.map((s, i) => (
              <LandingRow key={s.title} i={i} title={s.title} text={s.text} />
            ))}
          </ol>
        </div>
      </section>

      <section className="landing-section alt full-bleed" aria-labelledby="who-heading">
        <div className="container">
          <SectionIndex n={3} label="Who it's for" />
          <h2 id="who-heading">Who it&apos;s for</h2>
          <ul className="row-list">
            {AUDIENCES.map((a, i) => (
              <LandingRow key={a.title} i={i} title={a.title} text={a.text} />
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

      <section className="landing-section full-bleed" aria-labelledby="trust-heading">
        <div className="container">
          <SectionIndex n={4} label="Trust & privacy" />
          <h2 id="trust-heading">Trust &amp; privacy</h2>
          <ul className="row-list">
            {TRUST.map((title, i) => (
              <LandingRow key={title} i={i} title={title} />
            ))}
          </ul>
          <p className="muted landing-note">This prototype has no real authentication and runs locally only.</p>
        </div>
      </section>

      <section className="landing-section alt full-bleed" aria-labelledby="roadmap-heading">
        <div className="container">
          <SectionIndex n={5} label="Roadmap" />
          <h2 id="roadmap-heading">Roadmap</h2>
          <ul className="row-list">
            {ROADMAP.map((title, i) => (
              <LandingRow key={title} i={i} title={title} />
            ))}
          </ul>
        </div>
      </section>

      <section className="landing-section full-bleed" aria-labelledby="demo-heading">
        <div className="container">
          <SectionIndex n={6} label="Demo" />
          <h2 id="demo-heading">Try the demo</h2>
          <div className="landing-cta">
            <Link href="/login" className="button-link">
              Sign in to the demo
              <ArrowRight size={16} strokeWidth={1.5} aria-hidden="true" />
            </Link>
            <p className="muted">Prototype with fictional demo data.</p>
          </div>
        </div>
      </section>
    </>
  );
}
