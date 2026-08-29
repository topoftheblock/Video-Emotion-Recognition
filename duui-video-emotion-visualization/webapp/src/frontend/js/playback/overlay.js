// @ts-check
/**
 * The canvas laid over the video: one box per face/person detection
 * near the current instant, tagged with that person's video-modality
 * emotion.
 *
 * Detections are sampled per frame rather than spanning a range, so
 * they are matched by nearest timestamp within a tolerance instead of
 * by window containment the way segments are.
 */

import { el } from "../lib/dom.js";
import { overlayEnabled, personColorFor, readableTextColor } from "../state.js";
import { renderActiveList } from "../panels/people.js";

const ctx = el.overlay.getContext("2d");

/** Seconds — detections are sampled per-frame, not continuous. */
const DETECTION_TOLERANCE = 0.15;

/** The row nearest to `t`, within `tolerance` seconds, or null. */
function nearestByTime(rows, t, tolerance) {
  let best = null;
  let bestDelta = Infinity;
  for (const r of rows) {
    if (r.t_time == null) continue;
    const delta = Math.abs(r.t_time - t);
    if (delta < bestDelta) {
      bestDelta = delta;
      best = r;
    }
  }
  return bestDelta <= tolerance ? best : null;
}

export function syncCanvasSize() {
  const rect = el.stageFrame.getBoundingClientRect();
  if (el.overlay.width !== rect.width || el.overlay.height !== rect.height) {
    el.overlay.width = rect.width;
    el.overlay.height = rect.height;
  }
}

export function renderBoundingBoxes(data, t) {
  syncCanvasSize();
  ctx.clearRect(0, 0, el.overlay.width, el.overlay.height);

  if (!overlayEnabled("bounding_boxes")) {
    renderActiveList([]);
    return;
  }

  const showVideoEmotion = overlayEnabled("video_emotion");
  const faceBox = nearestByTime(data.detections.face, t, DETECTION_TOLERANCE);
  const personBox = nearestByTime(data.detections.person, t, DETECTION_TOLERANCE);
  const activeLabels = [];

  for (const box of [faceBox, personBox]) {
    if (!box) continue;
    const color = personColorFor(box.person_id);
    const emotionLabel = showVideoEmotion ? findEmotionLabelForFrame(data, box) : null;
    drawBox(box, color, emotionLabel, labelFontPx());
    if (box === faceBox) {
      const person = data.persons.find((p) => p.person_id === box.person_id);
      activeLabels.push({
        color,
        name:
          (person && person.clip_label) ||
          (box.person_id ? `person ${box.person_id}` : "unidentified"),
        emotion: emotionLabel,
      });
    }
  }

  renderActiveList(activeLabels);
}

/** Video-modality BaseEmotion rows don't carry their own bbox — they
 * share `frame_index` with the detection they were computed from, so
 * that's the join key back to a label for this box. */
function findEmotionLabelForFrame(data, box) {
  const match = data.emotions.video.find(
    (e) => e.person_id === box.person_id && e.frame_index === box.frame_index,
  );
  return match ? match.dominant_label : null;
}

/**
 * Pixel size for the emotion tag drawn on the video.
 *
 * Canvas text is absolutely sized — it cannot inherit the rem scale
 * every stylesheet now uses, so it has to be recomputed from the root
 * font size instead. Without this the one piece of type in the app that
 * sits *on* the data would be the only piece that ignores the reader's
 * font-size setting.
 *
 * 0.75 is --text-xs, which is what this label was drawn at. Read once
 * per frame in renderBoundingBoxes() rather than once per box, since
 * getComputedStyle can force a style flush and there is no reason to
 * pay for it twice in the same pass.
 */
function labelFontPx() {
  const root = parseFloat(getComputedStyle(document.documentElement).fontSize);
  return (root || 16) * 0.75;
}

function drawBox(box, color, emotionLabel, fontPx) {
  const w = el.overlay.width;
  const h = el.overlay.height;
  const x = box.x * w;
  const y = box.y * h;
  const bw = box.w * w;
  const bh = box.h * h;

  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.strokeRect(x, y, bw, bh);

  if (emotionLabel) {
    // Ubuntu Mono, which is the family this app actually ships (see the
    // @font-face block in css/base.css). This asked for IBM Plex Mono,
    // which is not bundled and never has been — so every label drawn
    // here has been rendering in the generic monospace fallback. 700 is
    // what a request for 600 resolved to anyway, said outright.
    ctx.font = `700 ${fontPx}px "Ubuntu Mono", monospace`;
    const label = emotionLabel.toUpperCase();

    // Every offset below is a ratio of the font size rather than a
    // constant, or the box would stay put while the text inside it
    // grew. The ratios are the original constants over the 12px they
    // assumed: 5/12 padding, 16/12 tag height, 12/12 baseline.
    const padding = fontPx * 0.42;
    const tagHeight = fontPx * 1.34;
    const gap = 2;
    const textWidth = ctx.measureText(label).width;
    // Above the box, unless that would clip off the top of the frame.
    const tagY = y - (tagHeight + gap) >= 0 ? y - (tagHeight + gap) : y + bh + gap;

    ctx.fillStyle = color;
    ctx.fillRect(x, tagY, textWidth + padding * 2, tagHeight);
    // Was a hardcoded near-black: a second, independent copy of the
    // same decision readableTextColor() makes for the filter chip,
    // which happened to pass but had nothing keeping it passing if the
    // palette moved. One source now.
    ctx.fillStyle = readableTextColor(color);
    ctx.fillText(label, x + padding, tagY + fontPx);
  }
}
