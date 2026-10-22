import type { APIRoute } from "astro";
import { COOKIE } from "../lib/auth";

export const POST: APIRoute = ({ cookies, redirect }) => {
  cookies.delete(COOKIE, { path: "/" });
  return redirect("/login");
};
