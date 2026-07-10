"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getMessages, type Locale, type Messages } from "@/lib/i18n";

const LanguageContext = createContext<{ locale: Locale; messages: Messages; setLocale: (locale: Locale) => void } | null>(null);

export function LanguageProvider({ initialLocale, children }: { initialLocale: Locale; children: React.ReactNode }) {
  const router = useRouter();
  const [locale, setLocaleState] = useState<Locale>(initialLocale);
  useEffect(() => { document.documentElement.lang = locale; }, [locale]);
  const setLocale = (nextLocale: Locale) => {
    setLocaleState(nextLocale);
    document.cookie = `staticdrop_locale=${nextLocale}; path=/; max-age=31536000; samesite=lax`;
    document.documentElement.lang = nextLocale;
    router.refresh();
  };
  return <LanguageContext.Provider value={{ locale, messages: getMessages(locale), setLocale }}>{children}</LanguageContext.Provider>;
}

export function useI18n() {
  const context = useContext(LanguageContext);
  if (!context) throw new Error("useI18n must be used inside LanguageProvider");
  return context;
}
