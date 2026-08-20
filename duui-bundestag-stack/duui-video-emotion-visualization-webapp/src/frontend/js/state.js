/**
 * The one mutable object the panels share.
 *
 * Declared in full here rather than grown at runtime: every field the
 * app ever sets is listed below, so reading this file tells you what
 * state exists without grepping for assignments.
 */

/*
 * Okabe-Ito, the standard colour-vision-safe qualitative palette.
 *
 * These are not decoration: a person's colour is the *only* thing
 * linking a stroked box on the video to a name in the sidebar, so two
 * entries that collapse into each other under a common deficiency make
 * two people indistinguishable with no text fallback to recover from.
 *
 * The previous palette had five such pairs -- teal/light-blue collapsed
 * under tritanopia, teal/pink and orange/lime under deuteranopia, and
 * pink/grey under both red-green forms. These six hold a worst-case
 * separation of dE2000 11.1 across normal, protan, deutan and tritan
 * vision. tests/cvd_check.py is the check; run it before touching this.
 */
export const PERSON_COLORS = [
  "#e69f00",
  "#56b4e9",
  "#009e73",
  "#f0e442",
  "#d55e00",
  "#cc79a7",
];

/*
 * Fallback for a detection with no identified person.
 *
 * Light, not the mid-grey this used to be. Deficiency simulation leaves
 * lightness essentially intact while collapsing hue, so a grey in the
 * middle of the palette's lightness band is exactly where muted colours
 * land -- the old #8b94a3 sat at dE2000 2.6 from Okabe-Ito's mauve and
 * 5.8 from the previous palette's pink. Separating it by lightness
 * instead is the one axis a deficiency cannot take away: this clears
 * every palette entry by 13.7.
 */
export const UNKNOWN_PERSON_COLOR = "#c8c8d0";

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
   * User-facing subtitle switch, on until the CC button turns it off.
   * Independent of `activeOverlays`: the agent decides which overlays
   * are *relevant*, this decides whether the bar is wanted at all.
   */
  subtitlesVisible: true,
  /**
   * null = the emotion panels describe everyone in the video (their
   * readings averaged together). Set by clicking a row in the People
   * panel, which narrows all three panels -- live readings *and*
   * whole-video averages -- to that one person's readings.
   */
  selectedPersonId: null,
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

/** sRGB relative luminance of a `#rrggbb` string, per WCAG 2.x. */
function relativeLuminance(hex) {
  const c = hex.replace("#", "");
  const channel = (i) => {
    const s = parseInt(c.slice(i, i + 2), 16) / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * channel(0) + 0.7152 * channel(2) + 0.0722 * channel(4);
}

/** WCAG contrast ratio between two `#rrggbb` strings. */
function contrastRatio(a, b) {
  const la = relativeLuminance(a);
  const lb = relativeLuminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

/**
 * Pick a text colour that stays readable on `hex` as a background.
 *
 * Compares the two candidates and returns whichever actually contrasts
 * more. This used to threshold on luminance at `L > 0.45`, which is far
 * above the real crossover near L = 0.18 -- so four of the seven person
 * colours were handed white text at 2.2-3.1:1 on the emotion panels'
 * filter chip. A comparison has no threshold to get wrong and stays
 * correct if the palette changes, which is the point: it is called with
 * whatever PERSON_COLORS happens to hold.
 *
 * Every colour clears 4.5:1 against one of the two. The worst case is
 * the crossover itself, where both sit at about 4.58:1.
 */
export function readableTextColor(hex) {
  const dark = "#0b0e14";
  const light = "#ffffff";
  return contrastRatio(hex, dark) >= contrastRatio(hex, light) ? dark : light;
}

/** What to call a person: the importer's CLIP label, else their id. */
export function personName(person) {
  return person.clip_label || `person ${person.person_id}`;
}

/**
 * Alphabetical comparator for the person lists in the sidebar (People,
 * "also appears in", "on screen now"). `numeric: true` makes it a
 * natural sort -- "person 2" before "person 10" -- rather than the
 * lexicographic order plain string comparison would give.
 */
export function compareNames(a, b) {
  return a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" });
}
