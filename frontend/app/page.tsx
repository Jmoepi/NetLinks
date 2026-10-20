"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { ROLE_HOME, useIdentity } from "@/lib/identity";

/** Role-based redirect: SME -> /sme, Buyer -> /buyer, YES Admin -> /admin. */
export default function Home() {
  const { identity } = useIdentity();
  const router = useRouter();

  useEffect(() => {
    if (identity) router.replace(ROLE_HOME[identity.role]);
  }, [identity, router]);

  return <p>Opening your NetLinks workspace…</p>;
}
