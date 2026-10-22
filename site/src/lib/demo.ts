// Review mode (DEMO="true"): sample episodes, and nothing is read from or written to GitHub.
// Lets the site be previewed before the GitHub token exists.
import type { Episode, Feedback } from "./show";

export const isDemo = (env: { DEMO?: string }) => env.DEMO === "true";

export const DEMO_STATE: { next_plan_day: string; episodes: Episode[] } = {
  next_plan_day: "10-23",
  episodes: [
    { number: 3, date: "2026-10-22", title: "The Lord Who Provides", plan_day: "10-22", readings: [] },
    { number: 2, date: "2026-10-21", title: "Rest for the Weary", plan_day: "10-21", readings: [] },
    { number: 1, date: "2026-10-20", title: "In the Beginning, Mercy", plan_day: "10-20", readings: [] },
  ],
};

export const DEMO_FEEDBACK: Feedback[] = [
  { at: "2026-10-21T13:00:00Z", episode_date: "2026-10-21", episode_title: "Rest for the Weary",
    rating: "up", note: "Loved the part on Psalm 23. A little slower next time." },
];

export const DEMO_NOTICE = "This is a preview. Nothing you send here is saved.";
