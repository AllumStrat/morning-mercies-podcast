import plan from "../../../plan/navigators.json";

export type Episode = { number: number; date: string; title: string; plan_day: string; readings: string[]; seed?: boolean };
export type Settings = {
  voice: string;
  voice_speed: number;
  length: string;
  jump_to: string;
  focus: string;
  show_description: string;
  retention_days: number;
};
export type Feedback = { at: string; episode_date: string; episode_title: string; rating: "up" | "down" | ""; note: string };

// Kokoro voices the publishing step can render. The first letter picks the accent.
export const VOICES: [string, string][] = [
  ["af_heart", "Heart: warm, American"],
  ["af_bella", "Bella: bright, American"],
  ["af_nicole", "Nicole: soft, American"],
  ["af_sarah", "Sarah: clear, American"],
  ["af_kore", "Kore: calm, American"],
  ["bf_emma", "Emma: British"],
  ["bf_isabella", "Isabella: British"],
  ["am_michael", "Michael: American (the Old Paths voice)"],
  ["am_fenrir", "Fenrir: deeper, American"],
  ["bm_george", "George: British"],
];

// Must match LENGTHS in scripts/podcast.py.
export const LENGTHS: [string, string][] = [
  ["short", "Short, about 15 minutes"],
  ["medium", "Medium, about 22 minutes"],
  ["full", "Full, about 30 minutes"],
];

export const PLAN_DAYS = (plan.days as { id: string; readings: { track: string; passage: string }[] }[]).map((d) => {
  const [month, day] = d.id.split("-");
  const ot = d.readings.find((r) => r.track === "Old Testament")?.passage ?? d.readings[0].passage;
  return { id: d.id, label: `Month ${month}, Day ${day}: ${ot}` };
});

export const DEFAULT_SETTINGS: Settings = {
  voice: "af_heart",
  voice_speed: 1.0,
  length: "full",
  jump_to: "",
  focus: "",
  show_description: "",
  retention_days: 60,
};

// Must match the clamps in set_show() in scripts/podcast.py.
export const RETENTION = { min: 7, max: 120 };

export function cleanSettings(form: FormData, previous: Settings): Settings {
  const voice = String(form.get("voice") ?? "");
  const length = String(form.get("length") ?? "");
  const jump = String(form.get("jump_to") ?? "");
  const speed = Number(form.get("voice_speed"));
  const keep = Number(form.get("retention_days"));
  return {
    voice: VOICES.some(([id]) => id === voice) ? voice : previous.voice,
    voice_speed: Number.isFinite(speed) ? Math.min(1.3, Math.max(0.8, Math.round(speed * 20) / 20)) : previous.voice_speed,
    length: LENGTHS.some(([id]) => id === length) ? length : previous.length,
    // An empty pick means "keep going from where the show is", so the stored value stays.
    jump_to: PLAN_DAYS.some((d) => d.id === jump) ? jump : previous.jump_to,
    focus: String(form.get("focus") ?? "").slice(0, 1000).trim(),
    // Empty keeps the description in the show's config.json.
    show_description: String(form.get("show_description") ?? "").slice(0, 600).trim(),
    retention_days: Number.isInteger(keep) ? Math.min(RETENTION.max, Math.max(RETENTION.min, keep)) : previous.retention_days,
  };
}

export function parseSettings(text: string | null): Settings {
  try {
    return { ...DEFAULT_SETTINGS, ...(text ? JSON.parse(text) : {}) };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

export function parseFeedback(text: string | null): Feedback[] {
  return (text ?? "")
    .split("\n")
    .filter(Boolean)
    .flatMap((line) => {
      try {
        return [JSON.parse(line) as Feedback];
      } catch {
        return [];
      }
    });
}

/** The show's saved state, published with the feed on GitHub Pages. Null before the first episode. */
export async function loadState(env: Pick<Env, "PAGES_BASE" | "SHOW">) {
  const r = await fetch(`${env.PAGES_BASE}/${env.SHOW}/state/series.json?t=${Date.now()}`).catch(() => null);
  if (!r?.ok) return null;
  const state = (await r.json()) as { next_plan_day: string; episodes: Episode[] };
  return { next_plan_day: state.next_plan_day, episodes: state.episodes.filter((e) => !e.seed).reverse() };
}

export function planLabel(id: string | undefined): string {
  return PLAN_DAYS.find((d) => d.id === id)?.label ?? "";
}
