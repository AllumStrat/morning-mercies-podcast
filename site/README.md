# Morning Mercies settings site

A small password-protected site for Grace's show. It lists recent episodes so Grace can send
feedback, and has a settings page for voice, speaking speed, episode length, reading plan day,
and what the show should lean into.

It's an Astro site that runs as one Cloudflare Worker. Every save is a small commit to `main`
in this repo:

- feedback goes to `shows/grace/feedback.jsonl`, one line per submission
- settings go to `shows/grace/settings.json`

The 4am run reads both from its checkout, and `podcast.py next --show grace` passes them to the
writer in `work/today.json`. Nothing else has to change for a save to take effect the next morning.

## Deploys

The Worker `morning-mercies` on Jacob's Cloudflare account is connected to this repo with
Workers Builds: every push to `main` that touches `site/` builds and deploys it. It's live at
https://morning-mercies.jacob-274.workers.dev. `SESSION_SECRET` is already set. Add
`SITE_PASSWORD` and `GITHUB_TOKEN` in the Cloudflare dashboard (Workers & Pages, morning-mercies,
Settings, Variables and Secrets, type Secret). Until `SITE_PASSWORD` exists, no password works.

## Deploy by hand (only if Workers Builds is ever disconnected)

1. Create a fine-grained GitHub token: github.com, Settings, Developer settings, Fine-grained
   tokens. Resource owner AllumStrat, only the `morning-mercies-podcast` repository, permission
   Contents: Read and write. Nothing else.
2. From this folder:
   ```sh
   npm install
   npx wrangler login                      # Jacob's own Cloudflare account
   npx wrangler secret put SITE_PASSWORD   # what Grace types to get in
   npx wrangler secret put SESSION_SECRET  # paste the output of: openssl rand -hex 32
   npx wrangler secret put GITHUB_TOKEN    # the token from step 1
   npm run deploy
   ```
3. Custom domain. Worker custom domains need the zone on Cloudflare. If devbysalt.com's DNS is
   on Cloudflare, uncomment the `routes` line in `wrangler.jsonc` and deploy again; Cloudflare
   creates the DNS record for `morningmercies.devbysalt.com` itself. If the DNS is still at
   Porkbun, either move the nameservers to Cloudflare first, or keep using the `workers.dev`
   address the deploy prints.

Changing the password later: run `npx wrangler secret put SITE_PASSWORD` again. Changing
`SESSION_SECRET` signs everyone out.

## Review mode

Add `"DEMO": "true"` to `vars` in `wrangler.jsonc` (or `DEMO=true` in `.dev.vars`) to show sample
episodes and turn saving off. The pages say so at the top. It needs only `SITE_PASSWORD` and
`SESSION_SECRET`, so it's a safe way to review the site before the GitHub token exists. Remove it
for the real site.

## Local development

```sh
cp .dev.vars.example .dev.vars   # fill in a test password and secret
npm run build && npx wrangler dev
npm test                          # the GitHub save logic, offline
```

With a fake `GITHUB_TOKEN` the pages load and saves fail politely, which is the safe way to try it.
