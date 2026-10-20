"use client";

import type { ReactNode } from "react";
import { IdentityProvider, useIdentity } from "@/lib/identity";
import { Footer } from "./Footer";
import { TopBar } from "./TopBar";

function KeyedMain({ children }: { children: ReactNode }) {
  const { ready, identityKey } = useIdentity();
  // Render once the stored sign-in has been read (ready = hydrated). Re-mount the page when the account changes
  // so every screen reloads with the new headers; the key is "" while signed out.
  return (
    <main id="main" className="main container" tabIndex={-1} key={identityKey}>
      {ready ? children : <p>Loading…</p>}
    </main>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <IdentityProvider>
      <TopBar />
      <KeyedMain>{children}</KeyedMain>
      <Footer />
    </IdentityProvider>
  );
}
