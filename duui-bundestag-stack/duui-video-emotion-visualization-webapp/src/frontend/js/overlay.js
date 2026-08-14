/**
 * The canvas laid over the video: one box per face/person detection
 * near the current instant, tagged with that person's video-modality
 * emotion.
 *
 * Detections are sampled per frame rather than spanning a range, so
 * they are matched by nearest timestamp within a tolerance instead of
 * by window containment the way segments are.
 */

import { el } from "./dom.js";
import { overlayEnabled, personColorFor } from "./state.js";
import { renderActiveList } from "./panels/people.js";

const ctx = el.overlay.getContext("2d");

/** Seconds -- detections are sampled per-frame, not continuous. */
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
    drawBox(box, color, emotionLabel);
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

/** Video-modality BaseEmotion rows don't carry their own bbox -- they
 * share `frame_index` with the detection they were computed from, so
 * that's the join key back to a label for this box. */
function findEmotionLabelForFrame(data, box) {
  const match = data.emotions.video.find(
    (e) => e.person_id === box.person_id && e.frame_index === box.frame_index
  );
  return match ? match.dominant_label : null;
}

function drawBox(box, color, emotionLabel) {
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
    ctx.font = "600 12px 'IBM Plex Mono', monospace";
    const label = emotionLabel.toUpperCase();
    const padding = 5;
    const textWidth = ctx.measureText(label).width;
    // Above the box, unless that would clip off the top of the frame.
    const tagY = y - 18 >= 0 ? y - 18 : y + bh + 2;

    ctx.fillStyle = color;
    ctx.fillRect(x, tagY, textWidth + padding * 2, 16);
    ctx.fillStyle = "#0a0c0f";
    ctx.fillText(label, x + padding, tagY + 12);
  }
}
