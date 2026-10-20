import { CircleAlert, CircleCheck, Info } from "lucide-react";
import type { ReactNode } from "react";

const ICONS = { info: Info, success: CircleCheck, error: CircleAlert };

/** Status or error message announced to screen readers. */
export function Notice({ kind = "info", children }: { kind?: "info" | "error" | "success"; children: ReactNode }) {
  if (!children) return null;
  const Icon = ICONS[kind];
  return (
    <p className={`notice notice-${kind}`} role={kind === "error" ? "alert" : "status"}>
      <Icon size={16} strokeWidth={1.5} aria-hidden="true" />
      <span className="notice-body">{children}</span>
    </p>
  );
}
