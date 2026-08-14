/**
 * Playback: the transport controls, and the render loop everything
 * else hangs off.
 *
 * Nothing here knows what a subtitle or a bounding box is. Renderers
 * register with onFrame() and get called with (data, currentTime) --
 * on every animation frame while playing, and once per timeupdate/seek
 * while paused. That inversion is what keeps this module from having
 * to import every panel in the app.
 */

import { el } from "./dom.js";
import { formatClock } from "./format.js";
import { state } from "./state.js";

const frameSubscribers = [];

/** Register a renderer, called as callback(data, currentTime). */
export function onFrame(callback) {
  frameSubscribers.push(callback);
}

export function render() {
  const data = state.data;
  if (!data) return;
  const t = el.player.currentTime;
  for (const subscriber of frameSubscribers) {
    subscriber(data, t);
  }
  updateTransport(t);
}

export function seekTo(seconds) {
  el.player.currentTime = seconds;
}

/** Seek once the newly-loaded video knows its own duration. */
export function seekOnceLoaded(seconds) {
  el.player.addEventListener(
    "loadedmetadata",
    () => {
      el.player.currentTime = seconds;
    },
    { once: true }
  );
}

function updateTransport(t) {
  el.timeCurrent.textContent = formatClock(t);
  el.timeTotal.textContent = formatClock(el.player.duration || 0);
  // Left alone while the user is dragging it, or the scrub would fight
  // the pointer.
  if (!el.scrub.matches(":active")) {
    const pct = el.player.duration ? (t / el.player.duration) * 1000 : 0;
    el.scrub.value = pct;
  }
}

function loop() {
  render();
  if (!el.player.paused) {
    state.rafHandle = requestAnimationFrame(loop);
  }
}

/* Inline SVG rather than the ▶ / ⏸ glyphs these replace. Oxanium has
 * neither, so both came from whatever symbol font the OS fell back to
 * -- which is why they rendered at different sizes, and why only the
 * triangle sat off-centre: its glyph box carries a trailing side
 * bearing that the pause bars do not, so centring the box left the ink
 * pushed left.
 *
 * The triangle is centred by centroid, not by bounding box: (8.5 + 8.5
 * + 19) / 3 = 12, the centre of the viewBox. A triangle whose *box* is
 * centred reads as sitting too far left, which is the same illusion the
 * glyph was suffering from. The pause bars are symmetric, so box and
 * centroid coincide.
 *
 * Kept in sync with the initial markup in index.html. */
const ICON_PLAY =
  '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M8.5 5v14l10.5-7z"/></svg>';
const ICON_PAUSE =
  '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M8 5h3v14H8zm5 0h3v14h-3z"/></svg>';

export function initPlayer() {
  el.player.addEventListener("play", () => {
    el.playBtn.innerHTML = ICON_PAUSE;
    cancelAnimationFrame(state.rafHandle);
    loop();
  });

  el.player.addEventListener("pause", () => {
    el.playBtn.innerHTML = ICON_PLAY;
    cancelAnimationFrame(state.rafHandle);
    render();
  });

  el.player.addEventListener("seeked", render);
  el.player.addEventListener("timeupdate", () => {
    // While playing, the rAF loop already renders far more smoothly
    // than timeupdate fires; this is only for the paused case.
    if (el.player.paused) render();
  });

  el.playBtn.addEventListener("click", () => {
    if (el.player.paused) el.player.play();
    else el.player.pause();
  });

  el.scrub.addEventListener("input", () => {
    if (!el.player.duration) return;
    el.player.currentTime = (el.scrub.value / 1000) * el.player.duration;
  });
}
