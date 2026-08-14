/**
 * Every call to the backend, with one error policy.
 *
 * A non-2xx response throws, carrying the FastAPI `detail` string when
 * there is one -- callers that can carry on without the data (the
 * insights panel, the cross-video panel) catch and degrade, and the
 * ones that cannot let it surface.
 */

async function getJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`${path} failed (${response.status})`);
  }
  return response.json();
}

export function fetchVideos() {
  return getJson("/api/videos");
}

export function fetchVideoData(videoId) {
  return getJson(`/api/videos/${videoId}/data`);
}

export function fetchGlobalPersons() {
  return getJson("/api/persons/global");
}

export function fetchStats(videoId) {
  return getJson(`/api/stats/${videoId}`);
}

export async function askQuestion(question) {
  const response = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  const result = await response.json();
  if (!response.ok) {
    // The agent reports its own failures (unconfigured key, a query it
    // could not settle on) as `detail`; those are worth showing verbatim.
    throw new Error(result.detail || "The query agent could not answer that.");
  }
  return result;
}
