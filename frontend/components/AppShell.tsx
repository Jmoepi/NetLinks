"use client";

import type { ReactNode } from "react";
import { IdentityProvider, useIdentity } from "@/lib/identity";
import { TopBar } from "./TopBar";

function KeyedMain({ children }: { children: ReactNode }) {
  const { ready, identityKey } = useIdentity();
  // Re-mount the page when the demo role changes so every screen reloads with the new headers.
  return (
    <main id="main" className="main" tabIndex={-1} key={identityKey}>
      {ready ? children : <p>Loading…</p>}
    </main>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <IdentityProvider>
      <TopBar />
      <KeyedMain>{children}</KeyedMain>
    </IdentityProvider>
  );
}
