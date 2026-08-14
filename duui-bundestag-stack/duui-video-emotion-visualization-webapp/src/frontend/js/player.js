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
import { formatTime } from "./format.js";
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
  el.timeCurrent.textContent = formatTime(t);
  el.timeTotal.textContent = formatTime(el.player.duration || 0);
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

export function initPlayer() {
  el.player.addEventListener("play", () => {
    el.playBtn.textContent = "⏸";
    cancelAnimationFrame(state.rafHandle);
    loop();
  });

  el.player.addEventListener("pause", () => {
    el.playBtn.textContent = "▶";
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
