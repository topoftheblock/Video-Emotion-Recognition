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

import { el } from "./dom.js";
import { renderBoundingBoxes, syncCanvasSize } from "./overlay.js";
import { initPlayer, onFrame, render } from "./player.js";
import { renderSubtitle } from "./subtitles.js";
import { initAskPanel } from "./panels/ask.js";
import { renderEmotionPanels } from "./panels/emotions.js";
import { loadVideo, loadVideoList } from "./videoLoader.js";

// Registration order is render order.
onFrame(renderSubtitle);
onFrame(renderEmotionPanels);
onFrame(renderBoundingBoxes);

initPlayer();
initAskPanel();

el.videoSelect.addEventListener("change", (e) => loadVideo(Number(e.target.value)));

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
