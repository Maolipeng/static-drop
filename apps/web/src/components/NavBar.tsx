"use client";

/**
 * Shared navigation bar.
 */
import Link from "next/link";
import { useI18n } from "@/components/LanguageProvider";

export function NavBar() {
  const { messages, locale, setLocale } = useI18n();
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
          <Link
            href="/login"
            className="text-slate-600 transition hover:text-brand-600"
          >
            {locale === "zh" ? "登录" : "Sign in"}
          </Link>
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
