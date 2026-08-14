/**
 * The one mutable object the panels share.
 *
 * Declared in full here rather than grown at runtime: every field the
 * app ever sets is listed below, so reading this file tells you what
 * state exists without grepping for assignments.
 */

export const PERSON_COLORS = [
  "#49d3c8",
  "#e0a458",
  "#c77dff",
  "#7dd3fc",
  "#f472b6",
  "#a3e635",
];

/** Fallback for a detection with no identified person. */
export const UNKNOWN_PERSON_COLOR = "#8b94a3";

export const state = {
  /** Payload of the currently loaded video (GET /api/videos/:id/data). */
  data: null,
  /** GET /api/videos, kept so we can tell whether a file is playable. */
  videos: [],
  /** GET /api/persons/global, fetched once and filtered per video. */
  globalPersonClusters: [],
  /** person_id -> colour, stable for as long as one video is loaded. */
  personColor: new Map(),
  /** Handle of the in-flight requestAnimationFrame render loop. */
  rafHandle: null,
  /**
   * null = show every overlay (default browsing mode). Once a query
   * result is opened this becomes a Set of the overlay keys the agent
   * picked as relevant, and the renderers hide whatever isn't in it.
   */
  activeOverlays: null,
};

/** True if `key` (one of the backend's OVERLAY_CHOICES) should render. */
export function overlayEnabled(key) {
  return state.activeOverlays === null || state.activeOverlays.has(key);
}

export function assignPersonColors(persons) {
  state.personColor.clear();
  persons.forEach((p, i) => {
    state.personColor.set(p.person_id, PERSON_COLORS[i % PERSON_COLORS.length]);
  });
}

export function personColorFor(personId) {
  return state.personColor.get(personId) || UNKNOWN_PERSON_COLOR;
}
