"use client";

// Demo identity (role switcher) and AI mode state, shared by every screen.
// The selected identity is persisted in localStorage and sent as X-Demo-Role / X-Demo-Sme-Id headers.

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, errorMessage, setApiIdentity } from "./api";
import type { AiModeSettings, Identity, Role } from "./types";

const STORAGE_KEY = "netlinks.demoIdentity";
const DEFAULT_IDENTITY = { role: "sme" as Role, sme_slug: "thuto" };

interface IdentityContextValue {
  ready: boolean;
  identities: Identity[];
  identity: Identity | null;
  identityKey: string;
  setIdentity: (role: Role, smeSlug: string | null) => void;
  aiMode: AiModeSettings | null;
  refreshAiMode: () => Promise<void>;
  loadError: string | null;
}

const IdentityContext = createContext<IdentityContextValue | null>(null);

export function keyOf(role: string, smeSlug: string | null): string {
  return smeSlug ? `${role}:${smeSlug}` : role;
}

function readStored(): { role: Role; sme_slug: string | null } {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as { role?: Role; sme_slug?: string | null };
      if (parsed.role) return { role: parsed.role, sme_slug: parsed.sme_slug ?? null };
    }
  } catch {
    // ignore unreadable storage and fall back to the default identity
  }
  return DEFAULT_IDENTITY;
}

export function IdentityProvider({ children }: { children: ReactNode }) {
  const [identities, setIdentities] = useState<Identity[]>([]);
  const [selected, setSelected] = useState<{ role: Role; sme_slug: string | null } | null>(null);
  const [aiMode, setAiMode] = useState<AiModeSettings | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    const stored = readStored();
    setApiIdentity(stored);
    setSelected(stored);
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
    if (selected) void refreshAiMode();
  }, [selected, refreshAiMode]);

  const setIdentity = useCallback((role: Role, smeSlug: string | null) => {
    const next = { role, sme_slug: role === "sme" ? smeSlug : null };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    setApiIdentity(next);
    setSelected(next);
  }, []);

  const identity = useMemo(() => {
    if (!selected) return null;
    const match = identities.find((i) => i.role === selected.role && (i.sme_slug ?? null) === selected.sme_slug);
    if (match) return match;
    // Before the identity list loads, use a provisional label so pages can start loading.
    return { role: selected.role, sme_slug: selected.sme_slug, label: keyOf(selected.role, selected.sme_slug), name: "" };
  }, [identities, selected]);

  const value: IdentityContextValue = {
    ready: selected !== null,
    identities,
    identity,
    identityKey: selected ? keyOf(selected.role, selected.sme_slug) : "",
    setIdentity,
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
