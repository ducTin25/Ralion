import { NextResponse, type NextRequest } from "next/server";

import { isLocale, routing, stripLocale } from "@/i18n/routing";

const SESSION_COOKIE = "ralion_session";
const PROTECTED_PREFIXES = [
  "/admin",
  "/hr",
  "/projects",
  "/select-project",
  "/product-manager",
  "/user",
  "/onboarding",
  "/tasks",
  "/documents",
  "/policies",
  "/access",
  "/change-password",
  "/chat",
];

function requestLocale(pathname: string) {
  const segment = pathname.split("/")[1] ?? "";
  return isLocale(segment) ? segment : null;
}

function isProtected(pathname: string) {
  return PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const locale = requestLocale(pathname);

  if (!locale) {
    const redirect = request.nextUrl.clone();
    redirect.pathname =
      pathname === "/" ? `/${routing.defaultLocale}` : `/${routing.defaultLocale}${pathname}`;
    return NextResponse.redirect(redirect);
  }

  const internalPath = stripLocale(pathname);
  if (isProtected(internalPath) && !request.cookies.get(SESSION_COOKIE)) {
    const login = request.nextUrl.clone();
    login.pathname = `/${locale}/login`;
    login.search = "";
    login.searchParams.set("next", `${pathname}${search}`);
    return NextResponse.redirect(login);
  }

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-ralion-locale", locale);
  return NextResponse.next({ request: { headers: requestHeaders } });
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt|.*\\..*).*)"],
};
