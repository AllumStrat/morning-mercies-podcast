// Reads and writes Grace's files in the podcast repo with a fine-grained token.
// Each save is one small commit on the main branch; the 4am run reads them from there.

type GitHubEnv = Pick<Env, "GITHUB_REPO" | "GITHUB_BRANCH" | "GITHUB_TOKEN">;

function headers(env: GitHubEnv) {
  return {
    Authorization: `Bearer ${env.GITHUB_TOKEN}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "morning-mercies-site",
  };
}

function url(env: GitHubEnv, path: string) {
  return `https://api.github.com/repos/${env.GITHUB_REPO}/contents/${path.split("/").map(encodeURIComponent).join("/")}`;
}

function toBase64(text: string): string {
  const bytes = new TextEncoder().encode(text);
  let bin = "";
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(bin);
}

function fromBase64(b64: string): string {
  const bin = atob(b64.replace(/\n/g, ""));
  return new TextDecoder().decode(Uint8Array.from(bin, (c) => c.charCodeAt(0)));
}

export async function readFile(env: GitHubEnv, path: string): Promise<{ text: string; sha: string } | null> {
  const r = await fetch(`${url(env, path)}?ref=${encodeURIComponent(env.GITHUB_BRANCH)}`, { headers: headers(env) });
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`GitHub read ${path} failed: ${r.status}`);
  const body = (await r.json()) as { content: string; sha: string };
  return { text: fromBase64(body.content), sha: body.sha };
}

/** Read, change, and write back one file, retrying if another save landed in between. */
export async function updateFile(
  env: GitHubEnv,
  path: string,
  change: (current: string | null) => string,
  message: string,
): Promise<void> {
  for (let attempt = 1; attempt <= 3; attempt++) {
    const current = await readFile(env, path);
    const r = await fetch(url(env, path), {
      method: "PUT",
      headers: { ...headers(env), "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        content: toBase64(change(current?.text ?? null)),
        branch: env.GITHUB_BRANCH,
        ...(current ? { sha: current.sha } : {}),
        committer: { name: "Morning Mercies site", email: "morning-mercies@users.noreply.github.com" },
      }),
    });
    if (r.ok) return;
    if ((r.status === 409 || r.status === 422) && attempt < 3) continue; // someone else saved first
    throw new Error(`GitHub write ${path} failed: ${r.status}`);
  }
}

/**
 * Ask the "Remake episode" workflow to render the newest episode again with the saved voice and speed.
 * It runs on a pushed claude/remake-SHOW-TIME branch, so the token needs only Contents read and write.
 */
export async function requestRemake(env: GitHubEnv & Pick<Env, "SHOW">): Promise<void> {
  const base = `https://api.github.com/repos/${env.GITHUB_REPO}/git`;
  const head = await fetch(`${base}/ref/heads/${encodeURIComponent(env.GITHUB_BRANCH)}`, { headers: headers(env) });
  if (!head.ok) throw new Error(`GitHub read ${env.GITHUB_BRANCH} failed: ${head.status}`);
  const sha = ((await head.json()) as { object: { sha: string } }).object.sha;
  const r = await fetch(`${base}/refs`, {
    method: "POST",
    headers: { ...headers(env), "Content-Type": "application/json" },
    body: JSON.stringify({ ref: `refs/heads/claude/remake-${env.SHOW}-${Date.now()}`, sha }),
  });
  if (!r.ok) throw new Error(`GitHub remake request failed: ${r.status}`);
}
