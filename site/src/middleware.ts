import { defineMiddleware } from "astro:middleware";
import { COOKIE, validSession } from "./lib/auth";

// Everything except the sign-in page and episode audio needs Grace's password cookie.
export const onRequest = defineMiddleware(async (context, next) => {
  const { pathname } = context.url;
  if (pathname === "/login" || pathname.startsWith("/_astro/") || pathname === "/favicon.svg" || pathname.startsWith("/audio/")) return next();
  const env = context.locals.runtime.env;
  if (await validSession(context.cookies.get(COOKIE)?.value, env.SESSION_SECRET)) {
    const response = await next();
    response.headers.set("Cache-Control", "private, no-store");
    return response;
  }
  if (context.request.method !== "GET") return new Response("Sign in first.", { status: 401 });
  return context.redirect("/login");
});
