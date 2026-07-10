import { NavBar } from "@/components/NavBar";
import { CopyButton } from "@/components/CopyButton";
import { getDeployment, formatBytes, formatDate } from "@/lib/api";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getMessages } from "@/lib/i18n";
import { getRequestLocale } from "@/lib/i18n-server";

// Force dynamic rendering - don't prerender at build time (API not available during build)
export const dynamic = "force-dynamic";

export default async function DeploymentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const messages = getMessages(await getRequestLocale());

  let deployment;
  try {
    deployment = await getDeployment(id);
  } catch {
    notFound();
  }

  return (
    <div className="min-h-screen">
      <NavBar />
      <main className="mx-auto max-w-3xl px-4 py-12">
        {/* Success banner */}
        <div className="mb-8 rounded-2xl border border-green-200 bg-green-50 p-6 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-green-100">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
              className="h-6 w-6 text-green-600"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="m4.5 12.75 6 6 9-13.5"
              />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-green-800">{messages.detail.success}</h1>
          <p className="mt-1 text-sm text-green-600">
            {messages.detail.successHelp}
          </p>
        </div>

        {/* URL card */}
        <div className="mb-6 rounded-2xl border border-slate-200 bg-white p-6">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
            {messages.detail.liveUrl}
          </h2>
          <div className="flex items-center gap-2">
            <input
              readOnly
              value={deployment.url}
              className="flex-1 rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 font-mono text-sm text-slate-700 outline-none"
            />
            <CopyButton text={deployment.url} />
          </div>
          <a
            href={deployment.url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-brand-600 hover:text-brand-700"
          >
            {messages.detail.openSite}
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
              className="h-4 w-4"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M13.5 6H5.25A2.25 2.25 0 0 0 3 8.25v10.5A2.25 2.25 0 0 0 5.25 21h10.5A2.25 2.25 0 0 0 18 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"
              />
            </svg>
          </a>
        </div>

        {/* Details grid */}
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-3">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              {messages.detail.deployId}
            </p>
            <p className="mt-1 truncate font-mono text-sm text-slate-700">
              {deployment.id}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              {messages.detail.fileCount}
            </p>
            <p className="mt-1 text-lg font-semibold text-slate-700">
              {deployment.file_count.toLocaleString()}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              {messages.detail.totalSize}
            </p>
            <p className="mt-1 text-lg font-semibold text-slate-700">
              {formatBytes(deployment.total_size)}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              {messages.detail.source}
            </p>
            <p className="mt-1 truncate text-sm text-slate-700">
              {deployment.source_zip}
            </p>
          </div>
          {deployment.name && (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                {messages.detail.name}
              </p>
              <p className="mt-1 truncate text-sm text-slate-700">
                {deployment.name}
              </p>
            </div>
          )}
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              {messages.detail.deployedAt}
            </p>
            <p className="mt-1 text-sm text-slate-700">
              {formatDate(deployment.created_at)}
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-700"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
              className="h-4 w-4"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 4.5v15m7.5-7.5h-15"
              />
            </svg>
            {messages.detail.newDeployment}
          </Link>
          <Link
            href="/deployments"
            className="inline-flex items-center gap-1.5 rounded-lg bg-white px-4 py-2 text-sm font-medium text-slate-700 ring-1 ring-slate-300 transition hover:bg-slate-50"
          >
            {messages.detail.viewAll}
          </Link>
        </div>
      </main>
    </div>
  );
}
