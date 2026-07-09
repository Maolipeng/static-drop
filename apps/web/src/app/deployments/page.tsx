import { NavBar } from "@/components/NavBar";
import { listDeployments, formatBytes, formatDate } from "@/lib/api";
import Link from "next/link";

export default async function DeploymentsPage() {
  let deployments: Awaited<ReturnType<typeof listDeployments>>["deployments"] = [];
  let total = 0;
  let loadError: string | null = null;

  try {
    const result = await listDeployments(100, 0);
    deployments = result.deployments;
    total = result.total;
  } catch (err: unknown) {
    loadError =
      err && typeof err === "object" && "error" in err
        ? String((err as { error: unknown }).error)
        : "Failed to load deployments";
  }

  return (
    <div className="min-h-screen">
      <NavBar />
      <main className="mx-auto max-w-5xl px-4 py-12">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Deployment History</h1>
            <p className="mt-1 text-sm text-slate-500">
              {total} {total === 1 ? "deployment" : "deployments"} total
            </p>
          </div>
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-700"
          >
            New deployment
          </Link>
        </div>

        {loadError && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center">
            <p className="font-medium text-red-700">{loadError}</p>
          </div>
        )}

        {!loadError && deployments.length === 0 && (
          <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1}
              stroke="currentColor"
              className="mx-auto mb-4 h-12 w-12 text-slate-300"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M2.25 12.75V12A2.25 2.25 0 0 1 4.5 9.75h15A2.25 2.25 0 0 1 21.75 12v.75m-8.69-6.44-2.12-2.12a1.5 1.5 0 0 0-1.061-.44H4.5A2.25 2.25 0 0 0 2.25 6v12a2.25 2.25 0 0 0 2.25 2.25h15A2.25 2.25 0 0 0 21.75 18V9a2.25 2.25 0 0 0-2.25-2.25h-5.379a1.5 1.5 0 0 1-1.06-.44Z"
              />
            </svg>
            <p className="text-lg font-medium text-slate-600">No deployments yet</p>
            <p className="mt-1 text-sm text-slate-400">
              Upload your first static site to get started.
            </p>
            <Link
              href="/"
              className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-700"
            >
              Upload now
            </Link>
          </div>
        )}

        {!loadError && deployments.length > 0 && (
          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50">
                <tr>
                  <th className="px-4 py-3 font-semibold text-slate-600">Name / ID</th>
                  <th className="px-4 py-3 font-semibold text-slate-600">Files</th>
                  <th className="px-4 py-3 font-semibold text-slate-600">Size</th>
                  <th className="px-4 py-3 font-semibold text-slate-600">Deployed</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {deployments.map((d) => (
                  <tr key={d.id} className="transition hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <p className="font-medium text-slate-800">
                        {d.name || d.source_zip}
                      </p>
                      <p className="font-mono text-xs text-slate-400">{d.id}</p>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {d.file_count.toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {formatBytes(d.total_size)}
                    </td>
                    <td className="px-4 py-3 text-slate-500">
                      {formatDate(d.created_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/deployments/${d.id}`}
                        className="font-medium text-brand-600 hover:text-brand-700"
                      >
                        View →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
