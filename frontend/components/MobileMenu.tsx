"use client";

// Full-screen overlay navigation for narrow screens. Traps focus while open, closes on Escape,
// on link click and on route change, and returns focus to the button that opened it.

import { X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, type KeyboardEvent, type RefObject } from "react";

const FOCUSABLE = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

interface MobileMenuProps {
  id: string;
  open: boolean;
  onClose: () => void;
  links: { href: string; label: string }[];
  triggerRef: RefObject<HTMLButtonElement | null>;
}

export function MobileMenu({ id, open, onClose, links, triggerRef }: MobileMenuProps) {
  const ref = useRef<HTMLDivElement>(null);
  const pathname = usePathname();
  const lastPath = useRef(pathname);
  const wasOpen = useRef(false);

  // Close when the route changes (for example after following a link).
  useEffect(() => {
    if (pathname !== lastPath.current) {
      lastPath.current = pathname;
      if (open) onClose();
    }
  }, [pathname, open, onClose]);

  useEffect(() => {
    if (open) {
      wasOpen.current = true;
      const previous = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      ref.current?.querySelector<HTMLElement>("a[href]")?.focus();
      return () => {
        document.body.style.overflow = previous;
      };
    }
    if (wasOpen.current) {
      wasOpen.current = false;
      triggerRef.current?.focus();
    }
  }, [open, triggerRef]);

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
      return;
    }
    if (e.key !== "Tab" || !ref.current) return;
    const focusable = Array.from(ref.current.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
      (el) => !el.hasAttribute("disabled"),
    );
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;
    if (e.shiftKey && (active === first || !ref.current.contains(active))) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && (active === last || !ref.current.contains(active))) {
      e.preventDefault();
      first.focus();
    }
  }

  return (
    <div
      id={id}
      ref={ref}
      className={`mobile-menu${open ? " is-open" : ""}`}
      role="dialog"
      aria-modal="true"
      aria-label="Menu"
      aria-hidden={open ? undefined : true}
      inert={!open}
      onKeyDown={onKeyDown}
    >
      <button type="button" className="icon-button menu-close" aria-label="Close menu" onClick={onClose}>
        <X size={32} strokeWidth={1.5} aria-hidden="true" />
      </button>
      <nav aria-label="Menu navigation">
        <ul className="mobile-menu-list">
          {links.map((item) => (
            <li key={item.href}>
              <Link href={item.href} aria-current={pathname === item.href ? "page" : undefined} onClick={onClose}>
                {item.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      <p className="mobile-menu-note">Role switcher and AI mode stay in the header</p>
    </div>
  );
}
