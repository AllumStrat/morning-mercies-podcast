import type { APIRoute } from "astro";

// Podcast apps fetch episode audio here. GitHub serves release files as a download
// (application/octet-stream, attachment), which Apple Podcasts refuses to play, so this
// streams the same file back as audio/mpeg, inline, passing byte ranges through.
// Public on purpose: podcast apps can't sign in.
const TAG = /^ep-[a-z0-9-]+$/;
const FILE = /^[a-z0-9-]+\.mp3$/;
const PASS = ["content-length", "content-range", "etag", "last-modified"];

export const GET: APIRoute = async ({ params, request, locals }) => {
  const { tag = "", file = "" } = params;
  if (!TAG.test(tag) || !FILE.test(file)) return new Response("Not found", { status: 404 });
  const env = locals.runtime.env;
  const range = request.headers.get("range");
  const upstream = await fetch(`https://github.com/${env.GITHUB_REPO}/releases/download/${tag}/${file}`, {
    headers: range ? { range } : {},
    redirect: "follow",
  });
  if (upstream.status === 416) return new Response(null, { status: 416, headers: pick(upstream) });
  if (!upstream.ok) return new Response("Not found", { status: 404 });

  const headers = pick(upstream);
  headers.set("content-type", "audio/mpeg");
  headers.set("content-disposition", `inline; filename="${file}"`);
  headers.set("accept-ranges", "bytes");
  headers.set("cache-control", "public, max-age=86400");
  const body = request.method === "HEAD" ? null : upstream.body;
  if (!body) await upstream.body?.cancel();
  return new Response(body, { status: upstream.status, headers });
};

export const HEAD = GET;

function pick(res: Response) {
  const headers = new Headers();
  for (const name of PASS) {
    const value = res.headers.get(name);
    if (value) headers.set(name, value);
  }
  return headers;
}
