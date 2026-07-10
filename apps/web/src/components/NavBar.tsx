"use client";

/**
 * Shared navigation bar.
 */
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useI18n } from "@/components/LanguageProvider";

type CurrentUser = { id: string | null; email: string; is_admin: boolean };

export function NavBar() {
  const { messages, locale, setLocale } = useI18n();
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loadingUser, setLoadingUser] = useState(true);

  useEffect(() => {
    let active = true;
    fetch("/console-api/auth/me", { cache: "no-store" })
      .then(async (response) => (response.ok ? (await response.json()).user as CurrentUser : null))
      .then((currentUser) => { if (active) setUser(currentUser); })
      .catch(() => { if (active) setUser(null); })
      .finally(() => { if (active) setLoadingUser(false); });
    return () => { active = false; };
  }, []);

  async function logout() {
    await fetch("/console-api/auth/logout", { method: "POST" });
    setUser(null);
    router.refresh();
  }

  return (
    <nav className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
        <Link href="/" className="flex items-center gap-2 font-bold text-slate-900">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
              className="h-5 w-5"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"
              />
            </svg>
          </span>
          <span className="text-lg">StaticDrop</span>
        </Link>
        <div className="flex items-center gap-6 text-sm">
          <Link
            href="/"
            className="text-slate-600 transition hover:text-brand-600"
          >
            {messages.nav.upload}
          </Link>
          <Link
            href="/deployments"
            className="text-slate-600 transition hover:text-brand-600"
          >
            {messages.nav.history}
          </Link>
          <Link
            href="/settings"
            className="text-slate-600 transition hover:text-brand-600"
          >
            {messages.nav.settings}
          </Link>
          {!loadingUser && (user ? (
            <div className="flex items-center gap-2">
              <span className="max-w-44 truncate rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-600" title={user.email}>
                {user.id ? user.email : messages.auth.automation}{user.is_admin && user.id ? ` · ${messages.auth.admin}` : ""}
              </span>
              {user.id && <button type="button" onClick={logout} className="text-slate-600 transition hover:text-brand-600">{messages.auth.logout}</button>}
            </div>
          ) : (
            <Link href="/login" className="text-slate-600 transition hover:text-brand-600">
              {locale === "zh" ? "登录" : "Sign in"}
            </Link>
          ))}
          <button
            type="button"
            onClick={() => setLocale(locale === "en" ? "zh" : "en")}
            className="rounded-md border border-slate-200 px-2 py-1 text-xs font-medium text-slate-600 transition hover:border-brand-400 hover:text-brand-600"
            aria-label={messages.nav.switchTo}
          >
            {messages.nav.switchTo}
          </button>
        </div>
      </div>
    </nav>
  );
}
