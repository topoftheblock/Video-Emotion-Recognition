/**
 * The subtitle bar over the video -- and `coveredBy`, the "which rows
 * are live at this instant" helper every time-synced panel shares.
 */

import { el } from "./dom.js";
import { overlayEnabled } from "./state.js";

/** Rows whose [start_time, end_time] window covers `t`. */
export function coveredBy(rows, t) {
  return rows.filter(
    (r) => r.start_time != null && r.end_time != null && r.start_time <= t && t <= r.end_time
  );
}

export function renderSubtitle(data, t) {
  const showTranscript = overlayEnabled("transcript");
  const showTextEmotion = overlayEnabled("text_emotion");
  el.subtitleBar.style.display = showTranscript || showTextEmotion ? "" : "none";

  const sentence = coveredBy(data.sentences, t)[0];
  el.subtitleText.textContent = showTranscript && sentence ? sentence.text : "";

  const textEmotion = coveredBy(data.emotions.text, t)[0];
  el.subtitleEmotion.textContent =
    showTextEmotion && textEmotion ? textEmotion.dominant_label || "" : "";
}
