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
import { overlayEnabled, personName, state } from "../state.js";
import { coveredBy } from "../subtitles.js";

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

/** Model labels that are not the word a reader wants to see. */
const DISPLAY_LABELS = { "<unk>": "unknown" };

/**
 * Seconds. Video-modality readings are 20ms windows sampled every few
 * frames, so for most instants nothing covers `t` at all -- the
 * nearest sample within this distance stands in, the same way the
 * bounding-box overlay matches detections.
 */
const SAMPLE_TOLERANCE = 0.15;

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
    el[config.panel].querySelector("[data-emo-filter]").textContent = person
      ? personName(person)
      : "";

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

    // Row order in the markup is labels-then-dimensions, which is what
    // lets the per-frame update address rows by index instead of
    // re-querying the DOM.
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

    labels.forEach((label, i) => {
      setScoreRow(rows[i], scores ? scores.get(label) || 0 : null);
    });
    config.dimensions.forEach((dimension, j) => {
      setSignedRow(rows[labels.length + j], live.length ? meanDimension(live, dimension) : null);
    });
  }
}

/**
 * The readings that describe instant `t`: everything whose window
 * covers it, or -- for the frame-sampled video modality, where the
 * gaps between samples are larger than the samples themselves -- every
 * reading from the nearest sampled instant.
 *
 * More than one comes back whenever several people were read at the
 * same moment; the caller averages them, so a two-face frame reads as
 * the room rather than as whichever face happened to be first.
 */
function currentReadings(rows, t) {
  const covering = coveredBy(rows, t);
  if (covering.length) return covering;

  let nearest = null;
  let nearestDelta = Infinity;
  for (const row of rows) {
    if (row.start_time == null) continue;
    const midpoint =
      row.end_time == null ? row.start_time : (row.start_time + row.end_time) / 2;
    const delta = Math.abs(midpoint - t);
    if (delta < nearestDelta) {
      nearestDelta = delta;
      nearest = row;
    }
  }
  if (!nearest || nearestDelta > SAMPLE_TOLERANCE) return [];
  return rows.filter((row) => row.start_time === nearest.start_time);
}

/** label -> mean score across `readings`. */
function meanScores(readings, data) {
  const totals = new Map();
  for (const reading of readings) {
    for (const score of data.emotion_scores[reading.emotion_id] || []) {
      if (score.score == null) continue;
      const total = totals.get(score.label) || { sum: 0, n: 0 };
      total.sum += score.score;
      total.n += 1;
      totals.set(score.label, total);
    }
  }
  const means = new Map();
  for (const [label, { sum, n }] of totals) means.set(label, sum / n);
  return means;
}

/** Mean of one dimensional column across `readings`, or null if none carry it. */
function meanDimension(readings, key) {
  let sum = 0;
  let n = 0;
  for (const reading of readings) {
    if (reading[key] == null) continue;
    sum += reading[key];
    n += 1;
  }
  return n ? sum / n : null;
}

/** The model's own dominant_label for a single reading; the strongest
 * averaged label once several are in play. */
function dominantOf(readings, scores) {
  if (readings.length === 1 && readings[0].dominant_label) {
    return displayLabel(readings[0].dominant_label);
  }
  let best = null;
  let bestScore = -Infinity;
  for (const [label, score] of scores) {
    if (score > bestScore) {
      bestScore = score;
      best = label;
    }
  }
  return best && displayLabel(best);
}

/** The configured order first, then anything the data had that it didn't. */
function orderLabels(preferred, scores) {
  const present = preferred.filter((label) => scores.has(label));
  const extra = Array.from(scores.keys())
    .filter((label) => !preferred.includes(label))
    .sort();
  return [...present, ...extra];
}

function renderBody(config, labels, averageScores, averageDimensions, nReadings) {
  return html`<div class="emo-meta">
      <span class="emo-dominant" data-emo-dominant>—</span>
      <span class="emo-count">${nReadings} reading${nReadings === 1 ? "" : "s"}</span>
    </div>
    <div class="emo-legend"><span>now</span><span>avg</span></div>
    ${labels.map((label) => scoreRow(label, averageScores.get(label) || 0))}
    ${config.dimensions.map((dimension, j) => signedRow(dimension, averageDimensions[j]))}`;
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

function displayLabel(label) {
  return DISPLAY_LABELS[label] || label;
}

/**
 * Both clamps exist because these are raw model outputs, and the
 * panels state a range in the way they draw ("share of a full track",
 * "distance from the centre"). A value outside the range the model is
 * documented to produce is a data problem worth noticing in the
 * numbers, not one worth letting a bar overflow its track over.
 */
function clamp01(value) {
  return value == null ? 0 : Math.max(0, Math.min(1, value));
}

function clampSigned(value) {
  return value == null ? 0 : Math.max(-1, Math.min(1, value));
}

function formatScore(value) {
  return `${Math.round(clamp01(value) * 100)}%`;
}

function formatSigned(value) {
  const clamped = clampSigned(value);
  return (clamped >= 0 ? "+" : "") + clamped.toFixed(2);
}
