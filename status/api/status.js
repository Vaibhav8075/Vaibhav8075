// Live "latest push" card for the profile README: GET /api/status?theme=dark|light returns an SVG.
//
// Reads the public events feed, picks the newest push outside the profile repository, and looks
// up its commit message (push events no longer carry commits, only the head SHA). The feed is
// unordered and can lag by a few hours, so events are sorted here. Responses are cached at the
// edge for 10 minutes; set GITHUB_TOKEN in the Vercel project for a higher API rate limit.

const USER = "Vaibhav8075";
const SKIP = new Set([`${USER}/${USER}`]); // profile updates are not project work

// Same solid GitHub tones as the README cards (scripts/build.py).
const THEMES = {
  dark: { text: "#f0f6fc", muted: "#8b949e", border: "#30363d", surface: "#161b22", live: "#3fb950", idle: "#6e7681" },
  light: { text: "#1f2328", muted: "#59636e", border: "#d1d9e0", surface: "#f6f8fa", live: "#1a7f37", idle: "#8c959f" },
};
const SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif";
const MONO = "ui-monospace, 'SF Mono', 'JetBrains Mono', Menlo, Consolas, monospace";

async function github(path) {
  const headers = { "User-Agent": `${USER}-status`, Accept: "application/vnd.github+json" };
  if (process.env.GITHUB_TOKEN) headers.Authorization = `Bearer ${process.env.GITHUB_TOKEN}`;
  const res = await fetch(`https://api.github.com${path}`, { headers });
  if (!res.ok) throw new Error(`GitHub API ${res.status}`);
  return res.json();
}

async function latestPush() {
  const events = await github(`/users/${USER}/events/public?per_page=100`);
  const push = events
    .filter(e => e.type === "PushEvent" && !SKIP.has(e.repo.name))
    .sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
  if (!push) return null;
  const commit = await github(`/repos/${push.repo.name}/commits/${push.payload.head}`);
  return {
    repo: push.repo.name.split("/")[1].replace(/^-+|-+$/g, ""),
    branch: push.payload.ref.replace("refs/heads/", ""),
    message: commit.commit.message.split("\n")[0],
    at: new Date(push.created_at),
  };
}

function ago(date, now = new Date()) {
  const s = Math.max(0, (now - date) / 1000);
  const units = [["year", 31536000], ["month", 2592000], ["day", 86400], ["hour", 3600], ["minute", 60]];
  for (const [unit, size] of units) {
    const n = Math.floor(s / size);
    if (n >= 1) return `${n} ${unit}${n > 1 ? "s" : ""} ago`;
  }
  return "just now";
}

const esc = s => s.replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const clip = (s, n) => (s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s);

export function card(theme, push, { now = new Date(), failed = false } = {}) {
  const t = THEMES[theme];
  const fresh = push && now - push.at < 864e5; // pushed within the last day
  const status = push ? `LATEST PUSH · ${ago(push.at, now).toUpperCase()}` : "LATEST PUSH";
  const title = push ? esc(clip(push.repo, 48)) : failed ? `github.com/${USER}` : "No public pushes in the last 90 days";
  const message = push ? esc(clip(push.message, 82)) : failed ? "Live activity is unavailable right now." : "";
  const branch = push ? esc(clip(push.branch, 28)) : "";
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 112" width="800" height="112">
  <style>
    .mono { font-family: ${MONO}; } .sans { font-family: ${SANS}; }
    .label { font-size: 11px; fill: ${t.muted}; letter-spacing: 2px; }
    .repo { font-size: 18px; font-weight: 700; fill: ${t.text}; }
    .msg { font-size: 14px; fill: ${t.muted}; }
    .branch { font-size: 11px; fill: ${t.muted}; }
  </style>
  <rect x="14.5" y="0.5" width="771" height="111" rx="12" fill="${t.surface}" stroke="${t.border}"/>
  <circle cx="42" cy="31" r="4.5" fill="${fresh ? t.live : t.idle}"/>
  <text x="56" y="35" class="mono label">${status}</text>
  ${branch ? `<text x="762" y="35" text-anchor="end" class="mono branch">${branch}</text>` : ""}
  <text x="38" y="66" class="sans repo">${title}</text>
  ${message ? `<text x="38" y="91" class="sans msg">${message}</text>` : ""}
</svg>`;
}

export default async function handler(req, res) {
  const theme = new URL(req.url, "http://localhost").searchParams.get("theme") === "light" ? "light" : "dark";
  let body;
  try {
    body = card(theme, await latestPush());
    res.setHeader("Cache-Control", "public, max-age=300, s-maxage=600, stale-while-revalidate=3600");
  } catch (err) {
    console.error(err);
    body = card(theme, null, { failed: true });   // never claim "no pushes" when GitHub just didn't answer
    res.setHeader("Cache-Control", "public, max-age=60, s-maxage=60");
  }
  res.setHeader("Content-Type", "image/svg+xml; charset=utf-8");
  res.status(200).send(body);
}
