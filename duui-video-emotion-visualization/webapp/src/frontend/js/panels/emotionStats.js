// @ts-check
/**
 * Deriving displayable values from a set of emotion readings.
 *
 * Pure functions over plain data: no DOM, no shared state, nothing to mock.
 * Split out of `emotions.js` so that the panel is about rendering and this is
 * about arithmetic; the two were interleaved and neither read clearly.
 */

import { coveredBy } from "../subtitles.js";

/** Model labels that are not the word a reader wants to see. */
export const DISPLAY_LABELS = { "<unk>": "unknown" };

/**
 * Seconds. Video-modality readings are 20ms windows sampled every few
 * frames, so for most instants nothing covers `t` at all -- the
 * nearest sample within this distance stands in, the same way the
 * bounding-box overlay matches detections.
 */
export const SAMPLE_TOLERANCE = 0.15;

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
export function currentReadings(rows, t) {
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
export function meanScores(readings, data) {
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
export function meanDimension(readings, key) {
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
export function dominantOf(readings, scores) {
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
export function orderLabels(preferred, scores) {
  const present = preferred.filter((label) => scores.has(label));
  const extra = Array.from(scores.keys())
    .filter((label) => !preferred.includes(label))
    .sort();
  return [...present, ...extra];
}

export function displayLabel(label) {
  return DISPLAY_LABELS[label] || label;
}

/**
 * Both clamps exist because these are raw model outputs, and the
 * panels state a range in the way they draw ("share of a full track",
 * "distance from the centre"). A value outside the range the model is
 * documented to produce is a data problem worth noticing in the
 * numbers, not one worth letting a bar overflow its track over.
 */
export function clamp01(value) {
  return value == null ? 0 : Math.max(0, Math.min(1, value));
}

export function clampSigned(value) {
  return value == null ? 0 : Math.max(-1, Math.min(1, value));
}

export function formatScore(value) {
  return `${Math.round(clamp01(value) * 100)}%`;
}

export function formatSigned(value) {
  const clamped = clampSigned(value);
  return (clamped >= 0 ? "+" : "") + clamped.toFixed(2);
}
