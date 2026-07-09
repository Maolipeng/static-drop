import { NavBar } from "@/components/NavBar";
import { DropZone } from "@/components/DropZone";

export default function HomePage() {
  return (
    <div className="min-h-screen">
      <NavBar />
      <main className="mx-auto max-w-3xl px-4 py-12">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">
            Deploy your static site in seconds
          </h1>
          <p className="mt-2 text-slate-500">
            Drag and drop your build output <code className="rounded bg-slate-100 px-1.5 py-0.5 text-sm">.zip</code> —
            we&apos;ll handle validation, extraction, and hosting.
          </p>
        </div>
        <DropZone />
      </main>
    </div>
  );
}
