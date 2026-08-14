/**
 * "Emotion insights": the fixed statistics from GET /api/stats/:id.
 *
 * Non-critical -- a stats failure hides the panel and logs, rather
 * than blocking playback of a video that is otherwise fine.
 */

import { fetchStats } from "../api.js";
import { el, html } from "../dom.js";

export async function loadInsights(videoId) {
  el.insightsPanel.style.display = "none";
  try {
    renderInsights(await fetchStats(videoId));
  } catch (err) {
    console.warn("Could not load emotion insights", err);
  }
}

function renderInsights(stats) {
  const parts = [
    html`<div class="insights-section-title">Video vs. text agreement</div>`,
    renderAgreement(stats.modality_agreement),
    html`<div class="insights-section-title">Dominant-emotion distribution</div>`,
    renderDistribution(stats.emotion_distribution || []),
    html`<div class="insights-section-title">Average valence / arousal by person</div>`,
    renderPersonAverages(stats.person_averages || []),
  ];

  el.insightsBody.innerHTML = parts.join("");
  el.insightsPanel.style.display = "";
}

function renderAgreement(agreement) {
  if (!agreement || !agreement.n_compared) {
    return html`<div class="empty-hint">Not enough overlapping data to compare yet.</div>`;
  }
  return html`<div class="agreement-stat">
    <span class="agreement-value">${agreement.agreement_pct}%</span>
    <span class="agreement-caption"
      >of ${agreement.n_compared} sentence(s) agree on valence sign between video and text
      emotion</span
    >
  </div>`;
}

function renderDistribution(distribution) {
  const byModality = {};
  for (const row of distribution) {
    (byModality[row.modality] = byModality[row.modality] || []).push(row);
  }
  const modalities = Object.keys(byModality);
  if (!modalities.length) {
    return html`<div class="empty-hint">No emotion readings for this video.</div>`;
  }

  // Wrapped in html`` rather than returned as a bare array: renderInsights
  // joins its parts with "", and Array.join stringifies a nested array
  // with commas between the elements.
  return html`${modalities.map((modality) => {
    // Top 4, already sorted by count desc by the query.
    const rows = byModality[modality].slice(0, 4);
    const max = Math.max(...rows.map((r) => r.n));
    return html`<div class="dist-group">
      <div class="dist-group-label">${modality}</div>
      ${rows.map(
        (row) => html`<div class="dist-row">
          <span class="dist-row-label">${row.dominant_label}</span>
          <div class="dist-track">
            <div class="dist-fill" style="width:${max ? Math.round((row.n / max) * 100) : 0}%"></div>
          </div>
          <span class="dist-row-n">${row.n}</span>
        </div>`
      )}
    </div>`;
  })}`;
}

function renderPersonAverages(averages) {
  const byPerson = {};
  for (const row of averages) {
    (byPerson[row.person_id] = byPerson[row.person_id] || {
      clip_label: row.clip_label,
      modalities: [],
    }).modalities.push(row);
  }
  const personIds = Object.keys(byPerson);
  if (!personIds.length) {
    return html`<div class="empty-hint">No per-person emotion data for this video.</div>`;
  }

  return html`${personIds.map((pid) => {
    const entry = byPerson[pid];
    const modalityText = entry.modalities
      .map((m) => `${m.modality}: v${m.avg_valence.toFixed(2)} a${m.avg_arousal.toFixed(2)} (n=${m.n})`)
      .join(" · ");
    return html`<div class="person-avg-row">
      <span class="person-avg-name">${entry.clip_label}</span>
      <span class="person-avg-modalities">${modalityText}</span>
    </div>`;
  })}`;
}
