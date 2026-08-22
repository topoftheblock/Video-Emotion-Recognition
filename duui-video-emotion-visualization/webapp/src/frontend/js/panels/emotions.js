/**
 * The three per-modality emotion panels: text, audio and video.
 *
 * Each panel lists every label its model emits, with two numbers per
 * label: the reading at the current playhead, and the mean over the
 * whole video (drawn as a tick on the same track, so "is this moment
 * unusual for this video?" is one glance rather than one subtraction).
 * Audio and video additionally carry dimensional readings -- valence
 * and arousal, plus dominance for audio -- which are signed, and so
 * grow left/right from the centre of the track instead of from its
 * left edge.
 *
 * Rows are built once per video by initEmotionPanels() and afterwards
 * only updated in place by renderEmotionPanels(), which runs on every
 * animation frame: rebuilding ~25 rows of markup 60 times a second is
 * the one thing in this app that would actually cost something.
 */

import { el, html } from "../dom.js";
import { overlayEnabled, personColorFor, personName, readableTextColor, state } from "../state.js";
import { coveredBy } from "../subtitles.js";
import {
  DISPLAY_LABELS,
  SAMPLE_TOLERANCE,
  clamp01,
  clampSigned,
  currentReadings,
  displayLabel,
  dominantOf,
  formatScore,
  formatSigned,
  meanDimension,
  meanScores,
  orderLabels,
} from "./emotionStats.js";

/**
 * One entry per panel: where it renders, which overlay key gates it
 * (the Ask panel narrows these to what a query is about), the label
 * vocabulary in the order it should be listed, and the dimensional
 * readings that modality actually carries.
 *
 * The label lists are the three models' documented vocabularies. They
 * are presentation order and nothing else -- a label the data has but
 * this list doesn't is still shown, appended alphabetically, so a
 * re-trained model never silently loses a row.
 *
 * Text has no dimensional row on purpose: its readings are a label
 * distribution only, and the importer writes 0.0 into
 * valence/arousal/dominance for them rather than NULL, which would
 * otherwise render as a confident "no emotion at all".
 */
const PANELS = [
  {
    modality: "text",
    overlay: "text_emotion",
    panel: "textEmotionPanel",
    body: "textEmotionBody",
    labels: ["anger", "disgust", "fear", "joy", "sadness", "surprise", "neutral"],
    dimensions: [],
  },
  {
    modality: "audio",
    overlay: "audio_emotion",
    panel: "audioEmotionPanel",
    body: "audioEmotionBody",
    labels: [
      "angry",
      "disgusted",
      "fearful",
      "happy",
      "neutral",
      "other",
      "sad",
      "surprised",
      "<unk>",
    ],
    dimensions: ["valence", "arousal", "dominance"],
  },
  {
    modality: "video",
    overlay: "video_emotion",
    panel: "videoEmotionPanel",
    body: "videoEmotionBody",
    labels: [
      "Anger",
      "Contempt",
      "Disgust",
      "Fear",
      "Happiness",
      "Neutral",
      "Sadness",
      "Surprise",
    ],
    dimensions: ["valence", "arousal"],
  },
];


/** Built by initEmotionPanels(), read by renderEmotionPanels(). */
let tracks = [];

/**
 * This modality's readings, narrowed to the selected person while the
 * People panel has one.
 *
 * Both the per-frame render and the whole-video averages go through
 * here, which is the point: an average over everyone next to a live
 * reading for one person would be a comparison against a baseline
 * that isn't theirs. Readings with no person_id (video-modality
 * frames the importer couldn't attribute to anyone) drop out of a
 * filtered view -- they are not known to be this person's.
 */
function readingsFor(data, modality) {
  const readings = data.emotions[modality] || [];
  if (state.selectedPersonId == null) return readings;
  return readings.filter((r) => r.person_id === state.selectedPersonId);
}

/** The selected person's row in `data.persons`, if there is one. */
function selectedPerson(data) {
  if (state.selectedPersonId == null) return null;
  return data.persons.find((p) => p.person_id === state.selectedPersonId) || null;
}

export function initEmotionPanels(data) {
  tracks = [];

  const person = selectedPerson(data);

  for (const config of PANELS) {
    const readings = readingsFor(data, config.modality);
    const chip = el[config.panel].querySelector("[data-emo-filter]");
    if (person) {
      chip.textContent = personName(person);
      const bg = personColorFor(person.person_id);
      chip.style.background = bg;
      chip.style.color = readableTextColor(bg);
    } else {
      chip.textContent = "";
      chip.style.background = "";
      chip.style.color = "";
    }

    if (!readings.length) {
      // A modality this video has nothing for stays hidden, as before.
      // One the *selected person* has nothing for is a different
      // statement and worth making: the panel stays up and says so,
      // rather than vanishing as if the filter had broken something.
      el[config.panel].style.display = person ? "" : "none";
      el[config.body].innerHTML = person
        ? html`<p class="empty-hint">No ${config.modality} readings for this person.</p>`
        : "";
      continue;
    }

    const averageScores = meanScores(readings, data);
    const labels = orderLabels(config.labels, averageScores);
    const averageDimensions = config.dimensions.map((d) => meanDimension(readings, d));

    const body = el[config.body];
    body.innerHTML = renderBody(config, labels, averageScores, averageDimensions, readings.length);

    // Row order in the markup is dimensions-then-labels (the dimensional
    // readings -- valence/arousal/dominance -- sit at the top, under a
    // divider, which is what lets the per-frame update address rows by
    // index instead of re-querying the DOM.
    const fills = body.querySelectorAll("[data-emo-fill]");
    const values = body.querySelectorAll("[data-emo-now]");
    tracks.push({
      config,
      labels,
      dominant: body.querySelector("[data-emo-dominant]"),
      rows: Array.from(fills, (fill, i) => ({ fill, now: values[i] })),
    });

    el[config.panel].style.display = "";
  }
}

export function renderEmotionPanels(data, t) {
  for (const track of tracks) {
    const { config, labels, rows } = track;
    // A narrowed overlay set means the Ask panel decided this modality
    // isn't what the open result is about: the whole-video averages
    // stay (they are context, not a claim about this instant), the
    // live readings blank out.
    const live = overlayEnabled(config.overlay)
      ? currentReadings(readingsFor(data, config.modality), t)
      : [];
    const scores = live.length ? meanScores(live, data) : null;

    track.dominant.textContent = (scores && dominantOf(live, scores)) || "—";

    config.dimensions.forEach((dimension, j) => {
      setSignedRow(rows[j], live.length ? meanDimension(live, dimension) : null);
    });
    labels.forEach((label, i) => {
      setScoreRow(rows[config.dimensions.length + i], scores ? scores.get(label) || 0 : null);
    });
  }
}


function renderBody(config, labels, averageScores, averageDimensions, nReadings) {
  return html`<div class="emo-meta">
      <span class="emo-dominant" data-emo-dominant>—</span>
      <span class="emo-count">${nReadings} reading${nReadings === 1 ? "" : "s"}</span>
    </div>
    <div class="emo-legend"><span>now</span><span>avg</span></div>
    ${config.dimensions.map((dimension, j) => signedRow(dimension, averageDimensions[j]))}
    ${config.dimensions.length ? html`<hr class="emo-divider">` : ""}
    ${labels.map((label) => scoreRow(label, averageScores.get(label) || 0))}`;
}

function scoreRow(label, average) {
  return html`<div class="emo-row">
    <span class="emo-label">${displayLabel(label)}</span>
    <div class="emo-track">
      <div class="emo-fill" data-emo-fill></div>
      <div class="emo-avg-mark" style="left:${clamp01(average) * 100}%"></div>
    </div>
    <span class="emo-now" data-emo-now>—</span>
    <span class="emo-avg">${formatScore(average)}</span>
  </div>`;
}

function signedRow(dimension, average) {
  return html`<div class="emo-row emo-row-dim">
    <span class="emo-label">${dimension}</span>
    <div class="emo-track emo-track-signed">
      <div class="emo-fill" data-emo-fill></div>
      <div class="emo-avg-mark" style="left:${50 + clampSigned(average) * 50}%"></div>
    </div>
    <span class="emo-now" data-emo-now>—</span>
    <span class="emo-avg">${average == null ? "—" : formatSigned(average)}</span>
  </div>`;
}

function setScoreRow(row, value) {
  row.fill.style.left = "0%";
  row.fill.style.width = clamp01(value) * 100 + "%";
  row.now.textContent = value == null ? "—" : formatScore(value);
}

function setSignedRow(row, value) {
  const width = Math.abs(clampSigned(value)) * 50;
  row.fill.style.left = (clampSigned(value) >= 0 ? 50 : 50 - width) + "%";
  row.fill.style.width = width + "%";
  row.now.textContent = value == null ? "—" : formatSigned(value);
}
