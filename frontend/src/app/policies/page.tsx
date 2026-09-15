import { redirect } from "next/navigation";
import { getLocale } from "next-intl/server";

import { isLocale, localizePath } from "@/i18n/routing";

export default async function LegacyPoliciesPage() {
  const requestedLocale = await getLocale();
  const locale = isLocale(requestedLocale) ? requestedLocale : "vi";
  redirect(localizePath("/documents", locale));
}
