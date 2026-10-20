import { ROLE_HOME } from "@/lib/identity";
import type { Role } from "@/lib/types";

/** Navigation links per demo role, shared by the desktop nav and the mobile overlay menu. */
export const NAV: Record<Role, { href: string; label: string }[]> = {
  sme: [
    { href: "/sme", label: "My profile" },
    { href: "/sme/readiness", label: "Readiness" },
  ],
  buyer: [
    { href: "/buyer", label: "Opportunities" },
    { href: "/buyer/audit", label: "Audit log" },
  ],
  admin: [
    { href: "/admin", label: "YES dashboard" },
    { href: "/buyer/audit", label: "Audit log" },
  ],
};

export function belongsTo(role: Role, pathname: string): boolean {
  if (pathname.startsWith("/documents")) return true;
  return pathname === ROLE_HOME[role] || pathname.startsWith(`${ROLE_HOME[role]}/`);
}
