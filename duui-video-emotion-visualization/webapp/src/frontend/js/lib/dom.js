// @ts-check
/**
 * Element lookups, and HTML construction that escapes by default.
 *
 * Every panel builds its markup as a string and assigns it to
 * `innerHTML`. Doing that with a plain template literal means every
 * interpolation has to remember to escape — which is exactly the kind
 * of thing missed on the one line nobody re-reads. The `html` tag below
 * escapes every interpolated value unless it is already-built markup,
 * so the safe path is the default one.
 *
 * The casts on a few entries below carry no runtime check. They record
 * which tag `index.html` declares, so the code reading `.value` or
 * `.currentTime` off one is checked against the element that actually
 * has it. A missing id is still null, exactly as the lookup reports it.
 */

export const el = {
  videoSelect: /** @type {HTMLSelectElement} */ (
    document.getElementById("videoSelect")
  ),
  videoComboInput: /** @type {HTMLInputElement} */ (
    document.getElementById("videoComboInput")
  ),
  videoComboList: document.getElementById("videoComboList"),
  player: /** @type {HTMLVideoElement} */ (document.getElementById("player")),
  overlay: /** @type {HTMLCanvasElement} */ (document.getElementById("overlay")),
  stageFrame: document.getElementById("stageFrame"),
  subtitleBar: document.getElementById("subtitleBar"),
  subtitleBox: document.getElementById("subtitleBox"),
  subtitleText: document.getElementById("subtitleText"),
  subtitleEmotion: document.getElementById("subtitleEmotion"),
  subtitleToggle: /** @type {HTMLInputElement} */ (
    document.getElementById("subtitleToggle")
  ),
  playBtn: /** @type {HTMLButtonElement} */ (document.getElementById("playBtn")),
  scrub: /** @type {HTMLInputElement} */ (document.getElementById("scrub")),
  timeCurrent: document.getElementById("timeCurrent"),
  timeTotal: document.getElementById("timeTotal"),
  textEmotionPanel: document.getElementById("textEmotionPanel"),
  textEmotionBody: document.getElementById("textEmotionBody"),
  audioEmotionPanel: document.getElementById("audioEmotionPanel"),
  audioEmotionBody: document.getElementById("audioEmotionBody"),
  videoEmotionPanel: document.getElementById("videoEmotionPanel"),
  videoEmotionBody: document.getElementById("videoEmotionBody"),
  personLegend: document.getElementById("personLegend"),
  personLegendHelp: document.getElementById("personLegendHelp"),
  personList: document.getElementById("personList"),
  activeList: document.getElementById("activeList"),
  crossVideoPanel: document.getElementById("crossVideoPanel"),
  crossVideoList: document.getElementById("crossVideoList"),
  askForm: /** @type {HTMLFormElement} */ (document.getElementById("askForm")),
  askInput: /** @type {HTMLInputElement} */ (document.getElementById("askInput")),
  askSubmit: /** @type {HTMLButtonElement} */ (document.getElementById("askSubmit")),
  askReset: /** @type {HTMLButtonElement} */ (document.getElementById("askReset")),
  askStatus: document.getElementById("askStatus"),
  askResults: document.getElementById("askResults"),
  jobBanner: document.getElementById("jobBanner"),
  emptyState: document.getElementById("emptyState"),
  emptyStateTitle: document.getElementById("emptyStateTitle"),
  emptyStateDetail: document.getElementById("emptyStateDetail"),
  emptyStateCommand: document.getElementById("emptyStateCommand"),
};

/**
 * Escape a value for insertion into markup.
 *
 * @param {string} str
 * @returns {string}
 */
export function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

/**
 * Markup already safe to insert: built by `html`, or vouched for by
 * `raw`. Subclassing String means it still behaves like one everywhere
 * else — assigned to `innerHTML`, or joined.
 */
class SafeHtml extends String {}

/**
 * Vouch for markup assembled elsewhere.
 *
 * Never hand this a value that came from the database or the agent.
 *
 * @param {string} value
 * @returns {SafeHtml}
 */
export function raw(value) {
  return new SafeHtml(value);
}

/**
 * Render one interpolated value, escaping unless it is already markup.
 *
 * @param {unknown} value
 * @returns {string}
 */
function interpolate(value) {
  if (value === null || value === undefined || value === false) return "";
  if (value instanceof SafeHtml) return String(value);
  if (Array.isArray(value)) return value.map(interpolate).join("");
  return escapeHtml(String(value));
}

/**
 * Tagged template that escapes every interpolated value.
 *
 * Nested results and arrays of them pass through untouched, so a list
 * renders as one expression.
 *
 * @param {TemplateStringsArray} strings
 * @param {...unknown} values
 * @returns {SafeHtml}
 */
export function html(strings, ...values) {
  let out = strings[0];
  values.forEach((value, i) => {
    out += interpolate(value) + strings[i + 1];
  });
  return new SafeHtml(out);
}
