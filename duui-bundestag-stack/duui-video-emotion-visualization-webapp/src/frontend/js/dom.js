/**
 * Element lookups, and HTML construction that escapes by default.
 *
 * Every panel builds its markup as a string and assigns it to
 * innerHTML. Doing that with a plain template literal means each
 * interpolation has to remember escapeHtml() -- which is exactly the
 * kind of thing that gets missed on the one line nobody re-reads. The
 * html`` tag below escapes every interpolated value unless it is
 * already-built markup, so the safe path is the default one.
 */

export const el = {
  videoSelect: document.getElementById("videoSelect"),
  player: document.getElementById("player"),
  overlay: document.getElementById("overlay"),
  stageFrame: document.getElementById("stageFrame"),
  subtitleBar: document.getElementById("subtitleBar"),
  subtitleText: document.getElementById("subtitleText"),
  subtitleEmotion: document.getElementById("subtitleEmotion"),
  playBtn: document.getElementById("playBtn"),
  scrub: document.getElementById("scrub"),
  timeCurrent: document.getElementById("timeCurrent"),
  timeTotal: document.getElementById("timeTotal"),
  textEmotionPanel: document.getElementById("textEmotionPanel"),
  textEmotionBody: document.getElementById("textEmotionBody"),
  audioEmotionPanel: document.getElementById("audioEmotionPanel"),
  audioEmotionBody: document.getElementById("audioEmotionBody"),
  videoEmotionPanel: document.getElementById("videoEmotionPanel"),
  videoEmotionBody: document.getElementById("videoEmotionBody"),
  personList: document.getElementById("personList"),
  activeList: document.getElementById("activeList"),
  crossVideoPanel: document.getElementById("crossVideoPanel"),
  crossVideoList: document.getElementById("crossVideoList"),
  askForm: document.getElementById("askForm"),
  askInput: document.getElementById("askInput"),
  askSubmit: document.getElementById("askSubmit"),
  askReset: document.getElementById("askReset"),
  askStatus: document.getElementById("askStatus"),
  askResults: document.getElementById("askResults"),
  emptyState: document.getElementById("emptyState"),
  emptyStateTitle: document.getElementById("emptyStateTitle"),
  emptyStateDetail: document.getElementById("emptyStateDetail"),
  emptyStateCommand: document.getElementById("emptyStateCommand"),
};

export function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

/** Markup that is already safe to insert -- either built by html`` or
 * explicitly vouched for via raw(). Subclassing String means it still
 * behaves like one everywhere else (innerHTML assignment, .join). */
class SafeHtml extends String {}

/** Escape hatch for markup assembled elsewhere. Never hand it a value
 * that came from the database or the query agent. */
export function raw(value) {
  return new SafeHtml(value);
}

function interpolate(value) {
  if (value === null || value === undefined || value === false) return "";
  if (value instanceof SafeHtml) return String(value);
  if (Array.isArray(value)) return value.map(interpolate).join("");
  return escapeHtml(String(value));
}

/**
 * Tagged template that escapes every interpolated value. Nested
 * html`` results and arrays of them pass through untouched, so a list
 * renders as html`<ul>${items.map((i) => html`<li>${i.name}</li>`)}</ul>`.
 */
export function html(strings, ...values) {
  let out = strings[0];
  values.forEach((value, i) => {
    out += interpolate(value) + strings[i + 1];
  });
  return new SafeHtml(out);
}
