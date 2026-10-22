// @ts-check
import { defineConfig } from "astro/config";
import cloudflare from "@astrojs/cloudflare";

// Every page renders on the Worker, so each request is checked against the password cookie.
export default defineConfig({
  output: "server",
  adapter: cloudflare({ imageService: "passthrough" }),
  security: { checkOrigin: true },
});
