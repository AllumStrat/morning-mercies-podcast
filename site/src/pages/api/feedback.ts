import type { APIRoute } from "astro";
import { updateFile } from "../../lib/github";
import type { Feedback } from "../../lib/show";
import { isDemo } from "../../lib/demo";

// Runs each time Grace sends feedback: one line appended to shows/SHOW/feedback.jsonl.
export const POST: APIRoute = async ({ request, locals, redirect }) => {
  const env = locals.runtime.env;
  const form = await request.formData();
  const date = String(form.get("episode_date") ?? "");
  const rating = String(form.get("rating") ?? "");
  const entry: Feedback = {
    at: new Date().toISOString(),
    episode_date: /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : "",
    episode_title: String(form.get("episode_title") ?? "").slice(0, 300),
    rating: rating === "up" || rating === "down" ? rating : "",
    note: String(form.get("note") ?? "").slice(0, 2000).trim(),
  };
  if (!entry.episode_date || (!entry.rating && !entry.note)) return redirect(`/#ep-${entry.episode_date}`);
  if (isDemo(env)) return redirect(`/?demo=1#ep-${entry.episode_date}`);
  try {
    await updateFile(
      env,
      `shows/${env.SHOW}/feedback.jsonl`,
      (current) => (current ?? "").replace(/\n*$/, current ? "\n" : "") + JSON.stringify(entry) + "\n",
      `Feedback on ${entry.episode_date}`,
    );
  } catch (e) {
    console.error(e);
    return redirect(`/?error=1#ep-${entry.episode_date}`);
  }
  return redirect(`/?saved=1#ep-${entry.episode_date}`);
};
