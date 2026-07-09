import { NavBar } from "@/components/NavBar";
import { checkHealth } from "@/lib/api";

export default async function SettingsPage() {
  let health: Awaited<ReturnType<typeof checkHealth>> | null = null;
  let error: string | null = null;

  try {
    health = await checkHealth();
  } catch (err: unknown) {
    error =
      err && typeof err === "object" && "error" in err
        ? String((err as { error: unknown }).error)
        : "Failed to reach API";
  }

  const token = process.env.NEXT_PUBLIC_DEPLOY_TOKEN || "";
  const hasToken = token.length > 0 && token !== "change-me-to-a-random-string";

  return (
    <div className="min-h-screen">
      <NavBar />
      <main className="mx-auto max-w-3xl px-4 py-12">
        <h1 className="mb-8 text-2xl font-bold text-slate-900">Settings</h1>

        {/* Health status */}
        <section className="mb-6 rounded-2xl border border-slate-200 bg-white p-6">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
            System Health
          </h2>
          {error ? (
            <div className="flex items-center gap-2 text-red-600">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-red-500" />
              <span className="font-medium">Error: {error}</span>
            </div>
          ) : health ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span
                  className={`inline-block h-2.5 w-2.5 rounded-full ${
                    health.status === "ok" ? "bg-green-500" : "bg-yellow-500"
                  }`}
                />
                <span className="font-medium capitalize text-slate-700">
                  {health.status}
                </span>
              </div>
              <dl className="grid grid-cols-2 gap-2 text-sm">
                <dt className="text-slate-500">Database</dt>
                <dd className="font-medium capitalize text-slate-700">
                  {health.db}
                </dd>
                <dt className="text-slate-500">Data directory</dt>
                <dd className="font-medium capitalize text-slate-700">
                  {health.data_dir}
                </dd>
                <dt className="text-slate-500">Deployments path</dt>
                <dd className="font-mono text-xs text-slate-700">
                  {health.deployments_dir}
                </dd>
              </dl>
            </div>
          ) : null}
        </section>

        {/* Auth status */}
        <section className="mb-6 rounded-2xl border border-slate-200 bg-white p-6">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Authentication
          </h2>
          <div className="flex items-center gap-2">
            <span
              className={`inline-block h-2.5 w-2.5 rounded-full ${
                hasToken ? "bg-green-500" : "bg-red-500"
              }`}
            />
            <span className="font-medium text-slate-700">
              {hasToken ? "Token configured" : "Default token — please set DEPLOY_TOKEN"}
            </span>
          </div>
          <p className="mt-2 text-xs text-slate-400">
            Token is configured server-side via the <code>DEPLOY_TOKEN</code> environment variable.
          </p>
        </section>

        {/* Limits */}
        <section className="rounded-2xl border border-slate-200 bg-white p-6">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Upload Limits
          </h2>
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-lg bg-slate-50 p-3">
              <dt className="text-slate-500">Max zip size</dt>
              <dd className="font-semibold text-slate-700">100 MB</dd>
            </div>
            <div className="rounded-lg bg-slate-50 p-3">
              <dt className="text-slate-500">Max total (uncompressed)</dt>
              <dd className="font-semibold text-slate-700">500 MB</dd>
            </div>
            <div className="rounded-lg bg-slate-50 p-3">
              <dt className="text-slate-500">Max single file</dt>
              <dd className="font-semibold text-slate-700">50 MB</dd>
            </div>
            <div className="rounded-lg bg-slate-50 p-3">
              <dt className="text-slate-500">Max file count</dt>
              <dd className="font-semibold text-slate-700">5,000</dd>
            </div>
          </dl>
          <p className="mt-3 text-xs text-slate-400">
            These limits can be overridden via environment variables on the API server.
          </p>
        </section>
      </main>
    </div>
  );
}
