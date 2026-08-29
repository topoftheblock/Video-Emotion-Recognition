// @ts-check
/**
 * Choosing and loading a video: the dropdown, the payload fetch, and
 * the panels that refresh once per video rather than once per frame.
 *
 * Also owns the empty state — the cover over the video frame for the
 * cases that otherwise just look like a broken app: nothing imported, a
 * database row whose file isn't in the store, and a payload that failed
 * to load.
 */

import { fetchGlobalPersons, fetchVideoData, fetchVideos } from "./lib/api.js";
import { el, html } from "./lib/dom.js";
import { assignPersonColors, state } from "./state.js";
import { renderCrossVideoPanel } from "./panels/crossVideo.js";
import { initEmotionPanels } from "./panels/emotions.js";
import { renderPersonList } from "./panels/people.js";

const IMPORT_COMMAND = "docker compose run --rm cas-to-postgres-importer";
const LOGS_COMMAND = "docker compose logs -f webapp";

// Marks the frame as covered, which is the one case where it is allowed
// to grow past 16:9 — see .stage-frame.is-empty in css/responsive.css
// for why that is safe only while this is up.
export function showEmptyState(title, detail, command) {
  el.emptyStateTitle.textContent = title;
  el.emptyStateDetail.textContent = detail;
  el.emptyStateCommand.textContent = command;
  el.emptyState.style.display = "";
  el.stageFrame.classList.add("is-empty");
}

export function hideEmptyState() {
  el.emptyState.style.display = "none";
  el.stageFrame.classList.remove("is-empty");
}

export async function loadVideoList() {
  let videos;
  try {
    videos = await fetchVideos();
  } catch (err) {
    console.error("Could not load the video list", err);
    showEmptyState(
      "Could not reach the webapp's API",
      "The page loaded, but /api/videos did not answer. The container is probably up without a working database connection — check its log:",
      LOGS_COMMAND,
    );
    return;
  }

  // An empty database used to render an empty dropdown over a blank
  // player with no explanation at all — indistinguishable from a broken
  // app. Say what is actually the case, and what to run.
  if (!videos.length) {
    showEmptyState(
      "No videos imported yet",
      "The webapp and the database are running fine — the database is simply empty. Run the importer, then reload this page:",
      IMPORT_COMMAND,
    );
    return;
  }

  // Kept so loadVideo() can tell whether the selected video's file is
  // actually in the store (GET /api/videos checks that per request).
  state.videos = videos;

  initVideoCombobox();
  applySelection(videos[0].video_id, false);

  // The global persons do not change per video load, so they are
  // fetched once and filtered in the browser.
  state.globalPersonClusters = await fetchGlobalPersons().catch(() => []);

  await loadVideo(videos[0].video_id);
}

/* --- The video picker ----------------------------------------------- */

/*
 * A searchable combobox: a text input that doubles as the search field,
 * with a list of matching filenames under it. The container carries a
 * `value` property holding the selected video and fires `change`, so
 * the rest of the app goes on treating it as the plain control it
 * replaced.
 */

let comboReady = false;
let selectedVideoId = null;
let comboHighlight = -1;

function initVideoCombobox() {
  if (comboReady) return;
  comboReady = true;

  // Expose .value on the container so el.videoSelect.value still works
  // for both reads and the Ask panel's programmatic selection.
  Object.defineProperty(el.videoSelect, "value", {
    configurable: true,
    get() {
      return selectedVideoId == null ? "" : String(selectedVideoId);
    },
    set(v) {
      applySelection(v == null || v === "" ? null : Number(v), false);
    },
  });

  el.videoComboInput.addEventListener("focus", () => {
    // Empty the field so the user types a fresh query rather than
    // filtering against the currently shown filename; the committed
    // selection is restored on blur if nothing new is picked.
    el.videoComboInput.value = "";
    openCombo();
  });
  el.videoComboInput.addEventListener("input", openCombo);
  el.videoComboInput.addEventListener("keydown", onComboKeydown);
  el.videoComboInput.addEventListener("blur", () =>
    setTimeout(() => {
      closeCombo();
      const current = state.videos.find((v) => v.video_id === selectedVideoId);
      el.videoComboInput.value = current ? current.filename : "";
    }, 120),
  );
  el.videoComboList.addEventListener("mousedown", (e) => {
    const item = /** @type {HTMLElement} */ (
      /** @type {Element} */ (e.target).closest("[data-video-id]")
    );
    if (item) applySelection(Number(item.dataset.videoId), true);
  });
  document.addEventListener("click", (e) => {
    if (!el.videoSelect.contains(/** @type {Node} */ (e.target))) closeCombo();
  });
}

/** Select a video, update the input, and optionally fire `change`. */
function applySelection(videoId, dispatch) {
  const video =
    videoId == null ? null : state.videos.find((v) => v.video_id === videoId);
  selectedVideoId = video ? video.video_id : null;
  el.videoComboInput.value = video ? video.filename : "";
  closeCombo();
  if (dispatch) el.videoSelect.dispatchEvent(new Event("change"));
}

/* aria-expanded belongs to whatever carries role="combobox" — that is
 * the input, not the #videoSelect wrapper these two used to write to. A
 * plain <div> may not carry the attribute at all, so the old pair
 * managed to be invalid markup *and* leave the input reading
 * "collapsed" for the life of the page. */
function openCombo() {
  renderVideoOptions();
  el.videoComboInput.setAttribute("aria-expanded", "true");
  el.videoComboList.hidden = false;
}

function closeCombo() {
  el.videoComboList.hidden = true;
  el.videoComboList.innerHTML = "";
  el.videoComboInput.setAttribute("aria-expanded", "false");
  // The options are gone, so a reference to one of them would dangle.
  el.videoComboInput.removeAttribute("aria-activedescendant");
  comboHighlight = -1;
}

/**
 * (Re)build the dropdown list from the full `state.videos` list, kept
 * in ascending filename order and narrowed to names containing the
 * input's text (case-insensitive).
 */
export function renderVideoOptions() {
  const query = el.videoComboInput.value.trim().toLowerCase();
  const matches = state.videos
    .filter((v) => v.filename.toLowerCase().includes(query))
    .sort((a, b) => a.filename.localeCompare(b.filename));

  // The id is what aria-activedescendant points at: an option that
  // cannot be referenced cannot be announced, which is why arrowing
  // through this list used to be silent.
  el.videoComboList.innerHTML = matches
    .map(
      (v) =>
        html`<li
          class="video-combo-item"
          role="option"
          id="videoComboOpt-${v.video_id}"
          aria-selected="false"
          data-video-id="${v.video_id}"
        >
          <span class="video-combo-name">${v.filename}</span>
          ${v.video_file_available ? "" : html`<span class="video-combo-missing">— file missing</span>`}
        </li>`,
    )
    .join("");

  // The rows just changed, so any previous index is meaningless — it
  // would point at whatever now happens to sit at that position.
  comboHighlight = -1;
  el.videoComboInput.removeAttribute("aria-activedescendant");
}

function onComboKeydown(e) {
  const items = Array.from(el.videoComboList.querySelectorAll(".video-combo-item"));
  if (e.key === "ArrowDown") {
    e.preventDefault();
    if (el.videoComboList.hidden) return openCombo();
    moveComboHighlight(items, 1);
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    if (el.videoComboList.hidden) return openCombo();
    moveComboHighlight(items, -1);
  } else if (e.key === "Enter") {
    if (!el.videoComboList.hidden && items[comboHighlight]) {
      e.preventDefault();
      applySelection(
        Number(/** @type {HTMLElement} */ (items[comboHighlight]).dataset.videoId),
        true,
      );
    }
  } else if (e.key === "Escape") {
    closeCombo();
  }
}

/**
 * Step the highlight, wrapping at both ends.
 *
 * The two keys used to be asymmetric: ArrowDown clamped at the last
 * item, ArrowUp clamped at the *first* and so could never get back to
 * "nothing highlighted" — which left neither key able to undo the
 * other. Wrapping makes them symmetric and keeps exactly one option
 * highlighted once navigation has started, so aria-activedescendant
 * always points at something that exists.
 *
 * From nothing, ArrowDown lands on the first option and ArrowUp on the
 * last, which is what a listbox is expected to do.
 */
function moveComboHighlight(items, step) {
  if (!items.length) return;
  const from = comboHighlight < 0 ? (step > 0 ? -1 : 0) : comboHighlight;
  comboHighlight = (from + step + items.length) % items.length;
  updateComboHighlight(items);
}

function updateComboHighlight(items) {
  items.forEach((it, i) => {
    const active = i === comboHighlight;
    it.classList.toggle("is-active", active);
    // The visual highlight and the announced one are the same state, so
    // they are set together rather than left to drift apart.
    it.setAttribute("aria-selected", active ? "true" : "false");
  });

  const active = items[comboHighlight];
  if (active) {
    el.videoComboInput.setAttribute("aria-activedescendant", active.id);
    active.scrollIntoView({ block: "nearest" });
  } else {
    el.videoComboInput.removeAttribute("aria-activedescendant");
  }
}

export async function loadVideo(videoId) {
  let data;
  try {
    data = await fetchVideoData(videoId);
  } catch (err) {
    console.error(`Could not load video ${videoId}`, err);
    showEmptyState(
      "Could not load this video's data",
      `The webapp asked for video #${videoId} and the request failed, so there is nothing to render. Check its log:`,
      LOGS_COMMAND,
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
      `The database has data for "${data.video.filename}", but that file is not in the video store, so there is nothing to play. Re-run the importer with the video beside its .xmi, then reload:`,
      IMPORT_COMMAND,
    );
  } else {
    hideEmptyState();
  }

  el.player.src = `/media/${encodeURIComponent(data.video.filename)}`;
  el.player.load();
}
