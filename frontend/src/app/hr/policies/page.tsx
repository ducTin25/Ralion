import { redirect } from "next/navigation";
import { getLocale } from "next-intl/server";

import { localizePath, type Locale } from "@/i18n/routing";

export default async function HrPoliciesPage() {
  const locale = (await getLocale()) as Locale;
  redirect(localizePath("/hr", locale));
}
