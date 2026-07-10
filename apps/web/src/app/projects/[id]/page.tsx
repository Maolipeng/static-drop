import Link from "next/link";
import { NavBar } from "@/components/NavBar";
import { RollbackButton } from "@/components/RollbackButton";
import { DomainManager } from "@/components/DomainManager";
import { getProjectDeployments, getProjectDomains } from "@/lib/server-api";
import { formatBytes, formatDate } from "@/lib/api";
import { getMessages } from "@/lib/i18n";
import { getRequestLocale } from "@/lib/i18n-server";

export const dynamic = "force-dynamic";

export default async function ProjectPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const messages = getMessages(await getRequestLocale());
  let data;
  let domains = [];
  try { [data, domains] = await Promise.all([getProjectDeployments(id), getProjectDomains(id)]); } catch { return <div className="p-12 text-center">{messages.deployments.loadError}</div>; }
  return <div className="min-h-screen"><NavBar /><main className="mx-auto max-w-5xl px-4 py-12">
    <Link href="/deployments" className="text-sm text-brand-600">← {messages.deployments.title}</Link>
    <h1 className="mt-4 text-2xl font-bold text-slate-900">{data.project.name}</h1>
    <p className="mt-1 font-mono text-sm text-slate-400">/p/{data.project.slug}/</p>
    <div className="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white"><table className="w-full text-left text-sm"><thead className="border-b bg-slate-50"><tr><th className="px-4 py-3">{messages.detail.version}</th><th className="px-4 py-3">{messages.deployments.size}</th><th className="px-4 py-3">{messages.deployments.deployed}</th><th className="px-4 py-3" /></tr></thead><tbody className="divide-y divide-slate-100">{data.deployments.map((deployment) => <tr key={deployment.id}><td className="px-4 py-3 font-semibold">v{deployment.version}{deployment.is_current && <span className="ml-2 rounded-full bg-green-100 px-2 py-1 text-xs text-green-700">current</span>}</td><td className="px-4 py-3">{formatBytes(deployment.total_size)}</td><td className="px-4 py-3 text-slate-500">{formatDate(deployment.created_at)}</td><td className="px-4 py-3 text-right"><Link className="mr-3 text-brand-600" href={`/deployments/${deployment.id}`}>{messages.deployments.view}</Link>{!deployment.is_current && <RollbackButton projectId={id} version={deployment.version} />}</td></tr>)}</tbody></table></div>
    <DomainManager projectId={id} initialDomains={domains} labels={{ title: messages.detail.domains, add: messages.detail.addDomain, auto: messages.detail.autoConfigureDomain, provisioned: messages.detail.dnsProvisioned, verify: messages.detail.verifyDomain, remove: messages.detail.removeDomain, verified: messages.detail.verified, pending: messages.detail.pending, placeholder: messages.detail.domainPlaceholder, failed: messages.detail.domainFailed }} />
  </main></div>;
}
