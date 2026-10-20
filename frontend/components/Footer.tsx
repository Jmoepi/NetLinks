import { Crosshair } from "lucide-react";

/** Small site footer in the reference "footer bottom" style. */
export function Footer() {
  return (
    <footer className="site-footer">
      <div className="footer-inner container">
        <div className="lockup">
          <Crosshair size={16} strokeWidth={1.5} aria-hidden="true" />
          <span aria-hidden="true">
            Net <span className="accent">/</span> Links
          </span>
          <span className="sr-only">NetLinks</span>
        </div>
        <p className="footer-note">
          Built for the YES AI Hackathon 2026 · Prototype with fictional demo data · No real authentication
        </p>
        <p className="footer-copy">© NetLinks prototype</p>
      </div>
    </footer>
  );
}
