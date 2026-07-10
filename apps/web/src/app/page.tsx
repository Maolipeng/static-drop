import { NavBar } from "@/components/NavBar";
import { DropZone } from "@/components/DropZone";
import { getMessages } from "@/lib/i18n";
import { getRequestLocale } from "@/lib/i18n-server";

export default async function HomePage() {
  const messages = getMessages(await getRequestLocale());
  return (
    <div className="min-h-screen">
      <NavBar />
      <main className="mx-auto max-w-3xl px-4 py-12">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">
            {messages.home.title}
          </h1>
          <p className="mt-2 text-slate-500">
            {messages.home.description}{" "}
            <code className="rounded bg-slate-100 px-1.5 py-0.5 text-sm">.zip</code>{" "}
            {messages.home.descriptionEnd}
          </p>
        </div>
        <DropZone />
      </main>
    </div>
  );
}
