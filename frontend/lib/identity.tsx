"use client";

// Simulated sign-in (demo identity) and AI mode state, shared by every screen.
// Signing in stores {role, sme_slug} in localStorage; a missing key means signed out. The selected identity is
// sent as X-Demo-Role / X-Demo-Sme-Id headers. No password is checked or stored: this is a demo simplification,
// production uses Amazon Cognito, and the API enforces role permissions server-side either way.

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, errorMessage, setApiIdentity } from "./api";
import type { AiModeSettings, Identity, Role } from "./types";

const STORAGE_KEY = "netlinks.demoIdentity";
const ROLES: Role[] = ["sme", "buyer", "admin"];

interface IdentityContextValue {
  /** True once localStorage has been read (signed-in state is known). */
  hydrated: boolean;
  /** Same as hydrated; kept for existing callers. */
  ready: boolean;
  signedIn: boolean;
  identities: Identity[];
  identity: Identity | null;
  identityKey: string;
  /** Signs in, or switches account when already signed in. */
  setIdentity: (role: Role, smeSlug: string | null) => void;
  signOut: () => void;
  aiMode: AiModeSettings | null;
  refreshAiMode: () => Promise<void>;
  loadError: string | null;
}

const IdentityContext = createContext<IdentityContextValue | null>(null);

export function keyOf(role: string, smeSlug: string | null): string {
  return smeSlug ? `${role}:${smeSlug}` : role;
}

function readStored(): { role: Role; sme_slug: string | null } | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as { role?: Role; sme_slug?: string | null };
      if (parsed.role && ROLES.includes(parsed.role)) return { role: parsed.role, sme_slug: parsed.sme_slug ?? null };
    }
  } catch {
    // unreadable storage counts as signed out
  }
  return null;
}

export function IdentityProvider({ children }: { children: ReactNode }) {
  const [identities, setIdentities] = useState<Identity[]>([]);
  const [selected, setSelected] = useState<{ role: Role; sme_slug: string | null } | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const [aiMode, setAiMode] = useState<AiModeSettings | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    const stored = readStored();
    setApiIdentity(stored);
    setSelected(stored);
    setHydrated(true);
    api
      .get<{ identities: Identity[] }>("/api/demo/identities")
      .then((res) => setIdentities(res.identities))
      .catch((err) => setLoadError(errorMessage(err)));
  }, []);

  const refreshAiMode = useCallback(async () => {
    try {
      setAiMode(await api.get<AiModeSettings>("/api/settings/ai-mode"));
    } catch {
      setAiMode(null);
    }
  }, []);

  useEffect(() => {
    // The AI mode endpoint needs an actor, so only ask for it when signed in.
    if (selected) void refreshAiMode();
    else setAiMode(null);
  }, [selected, refreshAiMode]);

  const setIdentity = useCallback((role: Role, smeSlug: string | null) => {
    const next = { role, sme_slug: role === "sme" ? smeSlug : null };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    setApiIdentity(next);
    setSelected(next);
  }, []);

  const signOut = useCallback(() => {
    window.localStorage.removeItem(STORAGE_KEY);
    setApiIdentity(null);
    setSelected(null);
  }, []);

  const identity = useMemo(() => {
    if (!selected) return null;
    const match = identities.find((i) => i.role === selected.role && (i.sme_slug ?? null) === selected.sme_slug);
    if (match) return match;
    // Before the identity list loads, use a provisional label so pages can start loading.
    return { role: selected.role, sme_slug: selected.sme_slug, label: keyOf(selected.role, selected.sme_slug), name: "" };
  }, [identities, selected]);

  const value: IdentityContextValue = {
    hydrated,
    ready: hydrated,
    signedIn: selected !== null,
    identities,
    identity,
    identityKey: selected ? keyOf(selected.role, selected.sme_slug) : "",
    setIdentity,
    signOut,
    aiMode,
    refreshAiMode,
    loadError,
  };

  return <IdentityContext.Provider value={value}>{children}</IdentityContext.Provider>;
}

export function useIdentity(): IdentityContextValue {
  const ctx = useContext(IdentityContext);
  if (!ctx) throw new Error("useIdentity must be used inside IdentityProvider");
  return ctx;
}

export const ROLE_HOME: Record<Role, string> = {
  sme: "/sme",
  buyer: "/buyer",
  admin: "/admin",
};
