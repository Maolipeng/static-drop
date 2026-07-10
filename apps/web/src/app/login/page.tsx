"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { useI18n } from "@/components/LanguageProvider";

export default function LoginPage() {
  const { messages } = useI18n();
  const router = useRouter();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setSuccess("");
    try {
      const response = await fetch(`/console-api/auth/${isRegister ? "register" : "login"}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        setError(payload?.error || messages.auth.failed);
        return;
      }
      setSuccess(messages.auth.loginSuccess);
      window.setTimeout(() => {
        router.push("/");
        router.refresh();
      }, 500);
    } catch {
      setError(messages.auth.failed);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md items-center px-4 py-12">
      <form onSubmit={submit} className="w-full rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="mb-6 text-2xl font-bold text-slate-900">
          {isRegister ? messages.auth.register : messages.auth.title}
        </h1>
        <label className="mb-1 block text-sm font-medium text-slate-700">{messages.auth.email}</label>
        <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2" />
        <label className="mb-1 block text-sm font-medium text-slate-700">{messages.auth.password}</label>
        <input required minLength={8} type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2" />
        {error && <p className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        {success && <p className="mb-4 rounded-lg bg-green-50 p-3 text-sm text-green-700">{success}</p>}
        <button disabled={loading} className="w-full rounded-lg bg-brand-600 px-4 py-2 font-medium text-white disabled:opacity-50">
          {loading ? "…" : isRegister ? messages.auth.register : messages.auth.submit}
        </button>
        <button type="button" onClick={() => setIsRegister((value) => !value)} className="mt-4 w-full text-sm text-brand-600 hover:text-brand-700">
          {isRegister ? messages.auth.switchLogin : messages.auth.switchRegister}
        </button>
      </form>
    </main>
  );
}
