import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { AppShell } from "@/components/AppShell";
import "./tokens.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "NetLinks (prototype)",
  description: "Evidenced, explainable procurement matching for youth-owned SMEs. Fictional demo data.",
  manifest: "/manifest.webmanifest",
  icons: { icon: "/icon.svg" },
};

export const viewport: Viewport = {
  themeColor: "#050505",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a href="#main" className="skip-link">
          Skip to main content
        </a>
        <div className="demo-banner" role="note">
          <span>
            <strong>Fictional demo data</strong> - every company, person, document and buyer shown here is fictional.
            Hackathon prototype with no real authentication.
          </span>
        </div>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
