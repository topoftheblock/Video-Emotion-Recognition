/**
 * The subtitle bar over the video -- and `coveredBy`, the "which rows
 * are live at this instant" helper every time-synced panel shares.
 */

import { el } from "./dom.js";
import { overlayEnabled, state } from "./state.js";

/** Rows whose [start_time, end_time] window covers `t`. */
export function coveredBy(rows, t) {
  return rows.filter(
    (r) => r.start_time != null && r.end_time != null && r.start_time <= t && t <= r.end_time
  );
}

/**
 * How far outside a row's window the playhead may sit and still count
 * as "on" that row, for the subtitle bar only.
 *
 * The sub-second gaps between sentences are an artefact of the token
 * timings the transcript is rebuilt from, not real silence. Without
 * this the caption blinks out between sentences -- and, worse, a video
 * sitting at 0:00 falls before the first sentence (which typically
 * starts a few hundredths in), so switching subtitles on at the
 * position every video opens at would show an empty bar.
 */
const SUBTITLE_GAP_TOLERANCE = 0.5;

/** The row covering `t`, else the nearest one within the tolerance. */
function rowAt(rows, t) {
  const covering = coveredBy(rows, t)[0];
  if (covering) return covering;

  let nearest = null;
  let nearestGap = Infinity;
  for (const row of rows) {
    if (row.start_time == null || row.end_time == null) continue;
    const gap = t < row.start_time ? row.start_time - t : t - row.end_time;
    if (gap < nearestGap) {
      nearest = row;
      nearestGap = gap;
    }
  }
  return nearestGap <= SUBTITLE_GAP_TOLERANCE ? nearest : null;
}

/** Wire the CC button. Takes the re-render to run on toggle so this
 * module keeps not knowing about the player. */
export function initSubtitleToggle(rerender) {
  el.subtitleToggle.addEventListener("click", () => {
    state.subtitlesVisible = !state.subtitlesVisible;
    syncToggleButton();
    rerender();
  });
  syncToggleButton();
}

function syncToggleButton() {
  const on = state.subtitlesVisible;
  el.subtitleToggle.classList.toggle("is-on", on);
  el.subtitleToggle.setAttribute("aria-pressed", String(on));
  el.subtitleToggle.title = on ? "Hide subtitles" : "Show subtitles";
}

export function renderSubtitle(data, t) {
  if (!state.subtitlesVisible) {
    el.subtitleBar.style.display = "none";
    return;
  }

  const showTranscript = overlayEnabled("transcript");
  const showTextEmotion = overlayEnabled("text_emotion");
  el.subtitleBar.style.display = showTranscript || showTextEmotion ? "" : "none";

  const sentence = rowAt(data.sentences, t);
  el.subtitleText.textContent = showTranscript && sentence ? sentence.text : "";

  const textEmotion = rowAt(data.emotions.text, t);
  el.subtitleEmotion.textContent =
    showTextEmotion && textEmotion ? textEmotion.dominant_label || "" : "";

  // The two lines share one background now (see .subtitle-box in
  // stage.css), so hiding an empty line can no longer take its
  // background with it via :empty -- both overlays can be on and still
  // land here with nothing to show for this instant (no sentence, or no
  // text-emotion reading, covering time t). Without this the box would
  // render as a blank translucent card.
  el.subtitleBox.style.display =
    el.subtitleText.textContent || el.subtitleEmotion.textContent ? "" : "none";
}
