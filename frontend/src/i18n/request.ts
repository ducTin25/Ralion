import { headers } from "next/headers";
import { getRequestConfig } from "next-intl/server";

import { loadMessages } from "./messages";
import { isLocale, routing } from "./routing";

export default getRequestConfig(async () => {
  const requestHeaders = await headers();
  const requested = requestHeaders.get("x-ralion-locale") ?? routing.defaultLocale;
  const locale = isLocale(requested) ? requested : routing.defaultLocale;

  return {
    locale,
    messages: await loadMessages(locale),
  };
});
