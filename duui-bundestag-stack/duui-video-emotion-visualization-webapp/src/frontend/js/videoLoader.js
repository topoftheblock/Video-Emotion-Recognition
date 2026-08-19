/**
 * Choosing and loading a video: the dropdown, the payload fetch, and
 * the panels that refresh once per video rather than once per frame.
 *
 * Also owns the empty state -- the cover over the video frame for the
 * cases that otherwise just look like a broken app: nothing imported,
 * a database row whose file isn't in the store, and a payload that
 * failed to load.
 */

import { fetchGlobalPersons, fetchVideoData, fetchVideos } from "./api.js";
import { el, html } from "./dom.js";
import { assignPersonColors, state } from "./state.js";
import { renderCrossVideoPanel } from "./panels/crossVideo.js";
import { initEmotionPanels } from "./panels/emotions.js";
import { renderPersonList } from "./panels/people.js";

const IMPORT_COMMAND = "docker compose run --rm importer";
const LOGS_COMMAND = "docker compose logs -f webapp";

export function showEmptyState(title, detail, command) {
  el.emptyStateTitle.textContent = title;
  el.emptyStateDetail.textContent = detail;
  el.emptyStateCommand.textContent = command;
  el.emptyState.style.display = "";
}

export function hideEmptyState() {
  el.emptyState.style.display = "none";
}

export async function loadVideoList() {
  let videos;
  try {
    videos = await fetchVideos();
  } catch (err) {
    console.error("Could not load the video list", err);
    showEmptyState(
      "Could not reach the viewer's API",
      "The page loaded, but /api/videos did not answer. The container is probably up without a working database connection — check its log:",
      LOGS_COMMAND
    );
    return;
  }

  // An empty database used to render an empty dropdown over a blank
  // player with no explanation at all -- indistinguishable from a
  // broken app. Say what is actually the case, and what to run.
  if (!videos.length) {
    showEmptyState(
      "No videos imported yet",
      "The viewer and the database are running fine — the database is simply empty. Run the import job, then reload this page:",
      IMPORT_COMMAND
    );
    return;
  }

  // Kept so loadVideo() can tell whether the selected video's file is
  // actually in the store (GET /api/videos checks that per request).
  state.videos = videos;

  el.videoSelect.innerHTML = videos
    .map(
      (v) =>
        html`<option value="${v.video_id}">
          ${v.filename}${v.video_file_available ? "" : " — file missing"}
        </option>`
    )
    .join("");

  // Cross-video person clusters don't change per video load -- fetched
  // once and filtered client-side in renderCrossVideoPanel().
  state.globalPersonClusters = await fetchGlobalPersons().catch(() => []);

  await loadVideo(videos[0].video_id);
}

export async function loadVideo(videoId) {
  let data;
  try {
    data = await fetchVideoData(videoId);
  } catch (err) {
    console.error(`Could not load video ${videoId}`, err);
    showEmptyState(
      "Could not load this video's data",
      `The viewer asked for video #${videoId} and the request failed, so there is nothing to render. Check the viewer's log:`,
      LOGS_COMMAND
    );
    return;
  }

  state.data = data;
  // person_ids are per video, so a selection carried over from the
  // previous one would filter every panel down to nothing.
  state.selectedPersonId = null;
  assignPersonColors(data.persons);
  renderPersonList(data.persons);
  renderCrossVideoPanel(data);
  initEmotionPanels(data);

  // A row can exist while its video file doesn't (import ran before the
  // file was placed, or it was removed afterwards). Say so instead of
  // letting playback fail silently on a black frame.
  const listed = state.videos.find((v) => v.video_id === videoId);
  if (listed && listed.video_file_available === false) {
    showEmptyState(
      "Video file missing",
      `The database has data for "${data.video.filename}", but that file is not in the video store, so there is nothing to play. Re-run the import job with the video next to its .xmi, then reload:`,
      IMPORT_COMMAND
    );
  } else {
    hideEmptyState();
  }

  el.player.src = `/media/${encodeURIComponent(data.video.filename)}`;
  el.player.load();
}
