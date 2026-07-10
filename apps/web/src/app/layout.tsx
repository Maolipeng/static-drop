import type { Metadata } from "next";
import "./globals.css";
import { LanguageProvider } from "@/components/LanguageProvider";
import { getRequestLocale } from "@/lib/i18n-server";

export const metadata: Metadata = {
  title: "StaticDrop — Drag & Drop Static Site Deployment",
  description: "Upload your static site build and get an instant live URL.",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const locale = await getRequestLocale();
  return (
    <html lang={locale}>
      <body className="min-h-screen antialiased">
        <LanguageProvider initialLocale={locale}>{children}</LanguageProvider>
      </body>
    </html>
  );
}
