/// <reference types="astro/client" />

type Env = {
  SHOW: string;
  SHOW_TITLE: string;
  GITHUB_REPO: string;
  GITHUB_BRANCH: string;
  PAGES_BASE: string;
  SITE_PASSWORD: string;
  SESSION_SECRET: string;
  GITHUB_TOKEN: string;
  DEMO?: string;
};

type Runtime = import("@astrojs/cloudflare").Runtime<Env>;

declare namespace App {
  interface Locals extends Runtime {}
}
