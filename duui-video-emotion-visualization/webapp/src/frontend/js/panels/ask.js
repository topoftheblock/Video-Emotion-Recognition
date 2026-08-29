// @ts-check
/**
 * The natural-language "Ask" panel.
 *
 * A question goes to POST /api/ask; the agent answers with SQL, an
 * explanation, the rows, and which overlays it thinks are relevant.
 * Rows that carry a video_id and a time come back as `segments` — those
 * render as a clickable list that seeks the player, and opening one
 * narrows the visible overlays to what the agent picked. "Reset view"
 * puts every overlay back.
 */

import { askQuestion } from "../lib/api.js";
import { el, html } from "../lib/dom.js";
import { formatMeta, formatTime } from "../lib/format.js";
import { render, seekOnceLoaded, seekTo } from "../playback/player.js";
import { state } from "../state.js";
import { loadVideo } from "../videoLoader.js";

/*
 * Whether a question is currently out.
 *
 * The submit button is marked aria-disabled while one is, rather than
 * actually disabled. `disabled` is simpler but removes the button from
 * the tab order the instant it is set — so a keyboard user who has just
 * pressed Enter or Space on it loses focus to the document body
 * mid-request, and has to tab in from the top of the page to reach the
 * answer they asked for. aria-disabled keeps the button where it is,
 * still focusable and still announced, and lets focus stay put.
 *
 * The trade is that aria-disabled enforces nothing: the browser will
 * happily submit the form again. That is what this flag is for, and why
 * the handler checks it before doing anything else.
 */
let pending = false;

/** Set the in-flight state, its announcement, and its look together. */
function setPending(busy) {
  pending = busy;
  el.askSubmit.setAttribute("aria-disabled", String(busy));
  // ask.css draws the spinner off aria-disabled, so the painted state
  // comes from this one call too.
  if (busy) el.askSubmit.setAttribute("aria-busy", "true");
  else el.askSubmit.removeAttribute("aria-busy");
}

function setAskStatus(message, isError) {
  el.askStatus.textContent = message || "";
  el.askStatus.classList.toggle("error", Boolean(isError));
}

function resetOverlaysToDefault() {
  state.activeOverlays = null;
  el.askResults.innerHTML = "";
  setAskStatus("");
  render();
}

function renderAskResults(result) {
  const parts = [];

  if (result.explanation) {
    parts.push(html`<div class="ask-explanation">${result.explanation}</div>`);
  }
  if (result.overlays && result.overlays.length) {
    parts.push(
      html`<div class="ask-overlays">
        ${result.overlays.map((o) => html`<span class="ask-overlay-tag">${o}</span>`)}
      </div>`,
    );
  }
  if (result.sql) {
    parts.push(html`<div class="ask-sql">${result.sql}</div>`);
  }

  if (result.segments && result.segments.length) {
    parts.push(
      html`<ul class="ask-segment-list">
        ${result.segments.map(
          (seg, i) =>
            html`<li>
              <button type="button" data-index="${i}">
                <span class="ask-segment-time"
                  >video #${seg.video_id} ·
                  ${formatTime(seg.start_time)}–${formatTime(seg.end_time)}</span
                >
                <span class="ask-segment-meta">${formatMeta(seg.meta || {})}</span>
              </button>
            </li>`,
        )}
      </ul>`,
    );
  } else if (result.rows && result.rows.length) {
    const cols = result.columns;
    parts.push(
      html`<div class="ask-table-wrap">
        <table class="ask-table">
          <thead>
            <tr>
              ${cols.map((c) => html`<th>${c}</th>`)}
            </tr>
          </thead>
          <tbody>
            ${result.rows.map(
              (row) =>
                html`<tr>
                  ${cols.map((c) => html`<td>${row[c] ?? ""}</td>`)}
                </tr>`,
            )}
          </tbody>
        </table>
      </div>`,
    );
  } else {
    parts.push(html`<div class="ask-explanation">No rows matched this question.</div>`);
  }

  if (result.truncated) {
    parts.push(
      html`<div class="ask-status">Showing the first ${result.rows.length} rows.</div>`,
    );
  }

  el.askResults.innerHTML = parts.join("");

  // One listener on the list rather than one per row: the rows are
  // <button>s, so Enter and Space arrive here as clicks without any key
  // handling of their own.
  el.askResults.querySelectorAll(".ask-segment-list").forEach((list) => {
    list.addEventListener("click", (event) => {
      const button = /** @type {HTMLElement} */ (
        /** @type {Element} */ (event.target).closest("[data-index]")
      );
      if (!button) return;
      jumpToSegment(result.segments[Number(button.dataset.index)], result.overlays);
    });
  });
}

async function jumpToSegment(seg, overlays) {
  state.activeOverlays = overlays && overlays.length ? new Set(overlays) : null;

  const needsVideoSwitch = !state.data || state.data.video.video_id !== seg.video_id;
  if (needsVideoSwitch) {
    await loadVideo(seg.video_id);
    // Sync the picker's display to the jumped-to video (the setter only
    // updates the visible value; loadVideo above did the actual
    // switch).
    el.videoSelect.value = String(seg.video_id);
    seekOnceLoaded(seg.start_time);
  } else {
    seekTo(seg.start_time);
  }
  render();
}

export function initAskPanel() {
  el.askForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    // aria-disabled stops nothing by itself — this is the line that
    // actually refuses a second question while the first is still out.
    // It also covers Enter from inside the input, which submits the
    // form without going near the button at all.
    if (pending) return;

    const question = el.askInput.value.trim();
    if (!question) return;

    // #askStatus is role="status" and announces "Thinking…", which is
    // the actual notification; setPending also marks the control itself
    // busy, so the state is discoverable by someone who navigates back
    // to it rather than only at the instant the live region fires.
    setPending(true);
    setAskStatus("Thinking…");
    el.askResults.innerHTML = "";

    try {
      const result = await askQuestion(question);
      setAskStatus(`${result.row_count} row(s).`);
      renderAskResults(result);
      if (result.segments && result.segments.length) {
        jumpToSegment(result.segments[0], result.overlays);
      }
    } catch (err) {
      setAskStatus(err.message, true);
    } finally {
      setPending(false);
    }
  });

  el.askReset.addEventListener("click", resetOverlaysToDefault);
}
