import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { headers } from "next/headers";
import { getTranslations } from "next-intl/server";

import { isLocale, routing } from "@/i18n/routing";

import "./globals.css";

/*
 * Hai font chỉ ĐĂNG KÝ biến CSS ở đây, không đặt làm font mặc định của body.
 * Chỉ khu vực Admin/HR (`.ralion-console`) tham chiếu tới chúng, nên các workspace
 * khác giữ nguyên diện mạo — đúng yêu cầu không đụng vào phần chung.
 */
const inter = Inter({
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["500"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("metadata");
  return {
    title: t("title"),
    description: t("description"),
    alternates: {
      languages: { vi: "/vi", en: "/en" },
    },
  };
}

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const requestHeaders = await headers();
  const requested = requestHeaders.get("x-ralion-locale") ?? routing.defaultLocale;
  const locale = isLocale(requested) ? requested : routing.defaultLocale;

  return (
    <html
      lang={locale}
      className={`h-full antialiased ${inter.variable} ${jetbrainsMono.variable}`}
      data-scroll-behavior="smooth"
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
