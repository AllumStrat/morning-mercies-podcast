// Password sign-in for one listener. The cookie holds an expiry and an HMAC of it, nothing else.

export const COOKIE = "mm_session";
const DAYS = 30;
const enc = new TextEncoder();

async function hmac(secret: string, data: string): Promise<Uint8Array> {
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return new Uint8Array(await crypto.subtle.sign("HMAC", key, enc.encode(data)));
}

function hex(bytes: Uint8Array): string {
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function sameBytes(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

export async function passwordMatches(input: string, expected: string, secret: string): Promise<boolean> {
  if (!expected || !secret) return false;
  // Compare digests so the check takes the same time whatever the input's length.
  return sameBytes(await hmac(secret, "pw:" + input), await hmac(secret, "pw:" + expected));
}

export async function newSession(secret: string): Promise<{ value: string; maxAge: number }> {
  const maxAge = DAYS * 24 * 60 * 60;
  const exp = String(Math.floor(Date.now() / 1000) + maxAge);
  return { value: `${exp}.${hex(await hmac(secret, "session:" + exp))}`, maxAge };
}

export async function validSession(value: string | undefined, secret: string): Promise<boolean> {
  if (!value || !secret) return false;
  const [exp, sig] = value.split(".");
  if (!exp || !sig || !/^\d+$/.test(exp) || Number(exp) < Date.now() / 1000) return false;
  return sameBytes(enc.encode(hex(await hmac(secret, "session:" + exp))), enc.encode(sig));
}
