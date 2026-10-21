import { Crosshair } from "lucide-react";

/** Minimal site footer with brand and copyright only. */
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
        <p className="footer-copy">© NetLinks prototype</p>
      </div>
    </footer>
  );
}
