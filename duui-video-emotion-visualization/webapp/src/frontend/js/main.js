/**
 * DUUI video review frontend -- entry point.
 *
 * Everything visible is driven off `video.currentTime`: renderers
 * register with the player's onFrame() and are handed
 * (payload, currentTime) on every animation frame while playing, and
 * once per seek/timeupdate while paused. They then pick out whichever
 * rows of the payload cover that instant -- subtitle text, the text
 * and audio emotion readouts, and bounding boxes for every detection
 * near this time.
 *
 * This module does the wiring and nothing else, which is what keeps
 * the renderers from having to import each other.
 */

import { el } from "./lib/dom.js";
import { renderBoundingBoxes, syncCanvasSize } from "./playback/overlay.js";
import { initPlayer, onFrame, render } from "./playback/player.js";
import { initSubtitleToggle, renderSubtitle } from "./playback/subtitles.js";
import { initAskPanel } from "./panels/ask.js";
import { initJobBanner } from "./panels/jobs.js";
import { initLegendDisclosures } from "./legend.js";
import { initEmotionPanels, renderEmotionPanels } from "./panels/emotions.js";
import { initPersonList } from "./panels/people.js";
import { state } from "./state.js";
import { loadVideo, loadVideoList } from "./videoLoader.js";

// Registration order is render order.
onFrame(renderSubtitle);
onFrame(renderEmotionPanels);
onFrame(renderBoundingBoxes);

initPlayer();
initSubtitleToggle(render);
initAskPanel();
initJobBanner();
initLegendDisclosures();

// Picking a person narrows the emotion panels to them. The rows are
// rebuilt rather than just re-filled: the whole-video averages drawn
// into the markup are that person's now, not the room's.
initPersonList(() => {
  if (!state.data) return;
  initEmotionPanels(state.data);
  render();
});

el.videoSelect.addEventListener("change", (e) =>
  loadVideo(Number(/** @type {HTMLSelectElement} */ (e.target).value)),
);

// The canvas is sized in CSS pixels off the stage, so it has to be
// resynced whenever the frame's box changes -- on a new video's
// metadata, and on any window resize.
el.player.addEventListener("loadedmetadata", () => {
  syncCanvasSize();
  render();
});

window.addEventListener("resize", () => {
  syncCanvasSize();
  render();
});

loadVideoList();
