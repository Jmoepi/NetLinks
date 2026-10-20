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

/** Whether a role may open a path (used to validate the sign-in `next` target; the API still decides). */
export function canAccess(role: Role, pathname: string): boolean {
  const under = (base: string) => pathname === base || pathname.startsWith(`${base}/`);
  if (under("/documents")) return true;
  if (under("/buyer/audit")) return role === "buyer" || role === "admin";
  if (under("/sme")) return role === "sme";
  if (under("/buyer")) return role === "buyer";
  if (under("/admin")) return role === "admin";
  return true;
}

export function belongsTo(role: Role, pathname: string): boolean {
  if (pathname.startsWith("/documents")) return true;
  return pathname === ROLE_HOME[role] || pathname.startsWith(`${ROLE_HOME[role]}/`);
}
