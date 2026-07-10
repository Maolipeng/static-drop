import { NavBar } from "@/components/NavBar";
import { checkHealth } from "@/lib/api";
import { getMessages } from "@/lib/i18n";
import { getRequestLocale } from "@/lib/i18n-server";

// Force dynamic rendering - don't prerender at build time (API not available during build)
export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const messages = getMessages(await getRequestLocale());
  let health: Awaited<ReturnType<typeof checkHealth>> | null = null;
  let error: string | null = null;

  try {
    health = await checkHealth();
  } catch (err: unknown) {
    error =
      err && typeof err === "object" && "error" in err
        ? String((err as { error: unknown }).error)
        : messages.common.failedToReachApi;
  }

  const token = process.env.DEPLOY_TOKEN || "";
  const hasToken = token.length > 0 && token !== "change-me-to-a-random-string";

  return (
    <div className="min-h-screen">
      <NavBar />
      <main className="mx-auto max-w-3xl px-4 py-12">
        <h1 className="mb-8 text-2xl font-bold text-slate-900">{messages.settings.title}</h1>

        {/* Health status */}
        <section className="mb-6 rounded-2xl border border-slate-200 bg-white p-6">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
            {messages.settings.systemHealth}
          </h2>
          {error ? (
            <div className="flex items-center gap-2 text-red-600">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-red-500" />
              <span className="font-medium">{messages.settings.error}: {error}</span>
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
                <dt className="text-slate-500">{messages.settings.database}</dt>
                <dd className="font-medium capitalize text-slate-700">
                  {health.db}
                </dd>
                <dt className="text-slate-500">{messages.settings.dataDirectory}</dt>
                <dd className="font-medium capitalize text-slate-700">
                  {health.data_dir}
                </dd>
                <dt className="text-slate-500">{messages.settings.deploymentsPath}</dt>
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
            {messages.settings.authentication}
          </h2>
          <div className="flex items-center gap-2">
            <span
              className={`inline-block h-2.5 w-2.5 rounded-full ${
                hasToken ? "bg-green-500" : "bg-red-500"
              }`}
            />
            <span className="font-medium text-slate-700">
              {hasToken ? messages.settings.tokenConfigured : messages.settings.defaultToken}
            </span>
          </div>
          <p className="mt-2 text-xs text-slate-400">
            {messages.settings.tokenHelp}
          </p>
        </section>

        {/* Limits */}
        <section className="rounded-2xl border border-slate-200 bg-white p-6">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
            {messages.settings.uploadLimits}
          </h2>
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-lg bg-slate-50 p-3">
              <dt className="text-slate-500">{messages.settings.maxZip}</dt>
              <dd className="font-semibold text-slate-700">100 MB</dd>
            </div>
            <div className="rounded-lg bg-slate-50 p-3">
              <dt className="text-slate-500">{messages.settings.maxUncompressed}</dt>
              <dd className="font-semibold text-slate-700">500 MB</dd>
            </div>
            <div className="rounded-lg bg-slate-50 p-3">
              <dt className="text-slate-500">{messages.settings.maxFile}</dt>
              <dd className="font-semibold text-slate-700">50 MB</dd>
            </div>
            <div className="rounded-lg bg-slate-50 p-3">
              <dt className="text-slate-500">{messages.settings.maxCount}</dt>
              <dd className="font-semibold text-slate-700">5,000</dd>
            </div>
          </dl>
          <p className="mt-3 text-xs text-slate-400">
            {messages.settings.limitsHelp}
          </p>
        </section>
      </main>
    </div>
  );
}
