// @ts-check
/**
 * The banner under the header: "an import is running, here is how far
 * it has got".
 *
 * The importer and the cross-video identity job write their progress to
 * `job_runs` (see each job's job_runs.py); this polls GET /api/jobs and
 * renders whatever is running. Nothing running means an empty,
 * collapsed banner — the page should look exactly as it did before this
 * feature existed for the 99% of the time no job is going.
 *
 * Polling is the whole cost of the feature, so it is kept honest in two
 * ways:
 *
 *   - **Nothing polls while the tab is hidden.** A backgrounded tab
 *     nobody is looking at is where the waste would be; the poll stops
 *     on visibilitychange and fires immediately on the way back, so
 *     returning to the tab shows current state rather than a stale
 *     banner.
 *   - **The interval backs off when there is nothing to watch.** Ten
 *     seconds while idle, two once a job is detected. Each poll is one
 *     new Postgres connection (see backend/db.py), so the idle rate is
 *     what the DB actually pays nearly all the time — roughly what
 *     the compose healthcheck already costs.
 */

import { fetchRunningJobs } from "../lib/api.js";
import { el, html } from "../lib/dom.js";

const POLL_IDLE_MS = 10000;
const POLL_ACTIVE_MS = 2000;

/** The job names the writers use, in the words a reader wants. */
const JOB_TITLES = {
  importer: "Import running",
  "global-identity": "Cross-video identity running",
};

let timer = null;

export function initJobBanner() {
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stopPolling();
    else poll();
  });

  if (!document.hidden) poll();
}

function stopPolling() {
  clearTimeout(timer);
  timer = null;
}

async function poll() {
  stopPolling();

  let jobs = [];
  try {
    jobs = (await fetchRunningJobs()).jobs || [];
  } catch (err) {
    // A failed poll is not worth a message of its own: the page works
    // without this banner, and whatever broke the request will be
    // shouting somewhere more useful.
    console.error("Could not read job status", err);
  }

  render(jobs);

  // Hidden between the request going out and coming back: don't
  // schedule another one for a tab nobody is watching.
  if (document.hidden) return;
  timer = setTimeout(poll, jobs.length ? POLL_ACTIVE_MS : POLL_IDLE_MS);
}

function render(jobs) {
  if (!jobs.length) {
    el.jobBanner.style.display = "none";
    el.jobBanner.innerHTML = "";
    return;
  }

  el.jobBanner.style.display = "";
  el.jobBanner.innerHTML = jobs.map(jobRow).join("");
}

function jobRow(job) {
  const title = JOB_TITLES[job.job] || `${job.job} running`;
  const detail = [job.phase, job.message].filter(Boolean).join(" — ");
  const counted = job.progress_total > 0 && job.progress_current != null;
  const percent = counted ? (job.progress_current / job.progress_total) * 100 : 0;

  // A job whose heartbeat has stopped is the one case where the banner
  // has to contradict its own row: the status still says running, but
  // nothing is writing it any more.
  if (job.stale) {
    return html`<div class="job-row job-row-stale">
      <span class="job-spinner job-spinner-stale" aria-hidden="true"></span>
      <div class="job-text">
        <strong>${title.replace(" running", " stopped responding")}</strong>
        <span class="job-detail"
          >No heartbeat for ${formatDuration(job.since_heartbeat_seconds)} — the job
          probably died. Check its log: docker compose logs ${job.job}</span
        >
      </div>
    </div>`;
  }

  return html`<div class="job-row">
    <span class="job-spinner" aria-hidden="true"></span>
    <div class="job-text">
      <strong>${title}</strong>
      <span class="job-detail">
        ${counted ? `${job.progress_current}/${job.progress_total}` : ""} ${detail}
        <span class="job-elapsed">${formatDuration(job.elapsed_seconds)}</span>
      </span>
      <!-- Determinate only when the job actually counts something.
           The importer's CAS parse can't, and a bar inching along on
           invented numbers would be worse than an honest stripe. -->
      <span class="job-bar${counted ? "" : " job-bar-indeterminate"}">
        <span class="job-bar-fill" style="width:${counted ? percent : 100}%"></span>
      </span>
    </div>
  </div>`;
}

/** "2m 14s" — long enough runs are the point, so hours count too. */
function formatDuration(seconds) {
  const total = Math.max(0, Math.round(seconds || 0));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours) return `${hours}h ${minutes}m`;
  if (minutes) return `${minutes}m ${secs}s`;
  return `${secs}s`;
}
