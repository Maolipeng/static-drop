"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { rollbackProject } from "@/lib/api";

export function RollbackButton({ projectId, version }: { projectId: string; version: number }) {
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  return <button type="button" disabled={loading} onClick={async () => { if (!window.confirm(`Rollback to v${version}?`)) return; setLoading(true); try { await rollbackProject(projectId, version); router.refresh(); } finally { setLoading(false); } }} className="text-amber-700 hover:text-amber-900 disabled:opacity-50">{loading ? "…" : "Rollback"}</button>;
}
