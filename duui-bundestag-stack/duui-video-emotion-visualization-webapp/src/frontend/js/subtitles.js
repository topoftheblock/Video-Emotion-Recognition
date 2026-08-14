/**
 * The two time-synced text readouts: the subtitle bar over the video,
 * and the "Voice" panel's valence/arousal bars.
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

export function renderVoicePanel(data, t) {
  const audioEmotion = overlayEnabled("audio_emotion")
    ? coveredBy(data.emotions.audio, t)[0]
    : null;
  if (!audioEmotion) {
    el.voiceLabel.textContent = "—";
    setBar(el.valenceFill, 0);
    setBar(el.arousalFill, 0);
    return;
  }
  el.voiceLabel.textContent = audioEmotion.dominant_label || "—";
  setBar(el.valenceFill, audioEmotion.valence || 0);
  setBar(el.arousalFill, audioEmotion.arousal || 0);
}

/** Renders a signed value in [-1, 1] as a bar growing left/right from centre. */
function setBar(elFill, value) {
  const clamped = Math.max(-1, Math.min(1, value || 0));
  const pct = Math.abs(clamped) * 50;
  if (clamped >= 0) {
    elFill.style.left = "50%";
    elFill.style.width = pct + "%";
  } else {
    elFill.style.left = 50 - pct + "%";
    elFill.style.width = pct + "%";
  }
}
