import { cookies, headers } from "next/headers";
import type { Locale } from "@/lib/i18n";

export async function getRequestLocale(): Promise<Locale> {
  const cookieLocale = (await cookies()).get("staticdrop_locale")?.value;
  if (cookieLocale === "en" || cookieLocale === "zh") return cookieLocale;
  const acceptLanguage = (await headers()).get("accept-language") || "";
  return acceptLanguage.toLowerCase().startsWith("zh") ? "zh" : "en";
}
