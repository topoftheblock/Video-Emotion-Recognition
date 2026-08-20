/**
 * The natural-language "Ask" panel.
 *
 * A question goes to POST /api/ask; the agent answers with SQL, an
 * explanation, the rows, and which overlays it thinks are relevant.
 * Rows that carry a video_id and a time come back as `segments` --
 * those render as a clickable list that seeks the player, and opening
 * one narrows the visible overlays to what the agent picked. "Reset
 * view" puts every overlay back.
 */

import { askQuestion } from "../api.js";
import { el, html } from "../dom.js";
import { formatMeta, formatTime } from "../format.js";
import { render, seekOnceLoaded, seekTo } from "../player.js";
import { state } from "../state.js";
import { loadVideo } from "../videoLoader.js";

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
        </div>`
    );
  }
  if (result.sql) {
    parts.push(html`<div class="ask-sql">${result.sql}</div>`);
  }

  if (result.segments && result.segments.length) {
    parts.push(
        html`<ul class="ask-segment-list">
          ${result.segments.map(
              (seg, i) => html`<li data-index="${i}">
            <span class="ask-segment-time"
            >video #${seg.video_id} · ${formatTime(seg.start_time)}–${formatTime(seg.end_time)}</span
            >
                <span class="ask-segment-meta">${formatMeta(seg.meta || {})}</span>
              </li>`
          )}
        </ul>`
    );
  } else if (result.rows && result.rows.length) {
    const cols = result.columns;
    parts.push(
        html`<div class="ask-table-wrap"><table class="ask-table">
          <thead>
          <tr>
            ${cols.map((c) => html`<th>${c}</th>`)}
          </tr>
          </thead>
          <tbody>
          ${result.rows.map(
              (row) => html`<tr>
                ${cols.map((c) => html`<td>${row[c] ?? ""}</td>`)}
              </tr>`
          )}
          </tbody>
        </table></div>`
    );
  } else {
    parts.push(html`<div class="ask-explanation">No rows matched this question.</div>`);
  }

  if (result.truncated) {
    parts.push(
        html`<div class="ask-status">Showing the first ${result.rows.length} rows.</div>`
    );
  }

  el.askResults.innerHTML = parts.join("");

  el.askResults.querySelectorAll(".ask-segment-list li").forEach((li) => {
    li.addEventListener("click", () => {
      jumpToSegment(result.segments[Number(li.dataset.index)], result.overlays);
    });
  });
}

async function jumpToSegment(seg, overlays) {
  state.activeOverlays = overlays && overlays.length ? new Set(overlays) : null;

  const needsVideoSwitch = !state.data || state.data.video.video_id !== seg.video_id;
  if (needsVideoSwitch) {
    await loadVideo(seg.video_id);
    // Sync the picker's display to the jumped-to video (the setter only
    // updates the visible value; loadVideo above did the actual switch).
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
    const question = el.askInput.value.trim();
    if (!question) return;

    el.askSubmit.disabled = true;
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
      el.askSubmit.disabled = false;
    }
  });

  el.askReset.addEventListener("click", resetOverlaysToDefault);
}
