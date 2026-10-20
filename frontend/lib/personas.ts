// Display helpers for the simulated sign-in personas. Demo emails are derived here for display only;
// no email or password is sent to the API or stored.

import type { Identity, Role } from "./types";

export const ROLE_NAMES: Record<Role, string> = { sme: "SME", buyer: "Buyer", admin: "YES Admin" };

/** Persona label used by the account menu (same texts as the former role-switcher options). */
export function personaLabel(i: Identity): string {
  if (i.role === "sme") return `SME - ${i.name}`;
  if (i.role === "buyer") return `Buyer - ${i.name} (Ubuntu Office Parks)`;
  return "YES Admin";
}

/** Short persona name shown in the sign-in persona step. */
export function personaName(i: Identity): string {
  if (i.role === "buyer") return `${i.name} (Ubuntu Office Parks)`;
  if (i.role === "admin") return "YES Admin";
  return i.name;
}

export function demoEmail(i: Pick<Identity, "role" | "sme_slug">): string {
  if (i.role === "sme") return `${i.sme_slug}@demo.netlinks.local`;
  if (i.role === "buyer") return "naledi@demo.netlinks.local";
  return "admin@demo.netlinks.local";
}
