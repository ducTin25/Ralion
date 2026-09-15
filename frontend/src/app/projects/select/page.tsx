import { redirect } from "next/navigation";
import { getLocale } from "next-intl/server";

import { localizePath, type Locale } from "@/i18n/routing";

export default async function ProjectsSelectPage() {
  const locale = (await getLocale()) as Locale;
  redirect(localizePath("/select-project", locale));
}
