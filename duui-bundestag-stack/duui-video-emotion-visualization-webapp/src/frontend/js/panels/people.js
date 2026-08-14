/**
 * The two person lists in the sidebar: everyone the importer
 * identified in this video, and whoever is on screen right now.
 */

import { el, html } from "../dom.js";
import { personColorFor } from "../state.js";

export function renderPersonList(persons) {
  if (!persons.length) {
    el.personList.innerHTML = '<li class="empty-hint">No identified persons.</li>';
    return;
  }
  el.personList.innerHTML = persons
    .map((p) => {
      const score = p.match_score != null ? `${Math.round(p.match_score * 100)}%` : "";
      return html`<li>
        <span class="person-swatch" style="background:${personColorFor(p.person_id)}"></span>
        ${p.clip_label || `person ${p.person_id}`}<span class="person-meta">${score}</span>
      </li>`;
    })
    .join("");
}

export function renderActiveList(labels) {
  if (!labels.length) {
    el.activeList.innerHTML = '<li class="empty-hint">No one detected at this frame.</li>';
    return;
  }
  el.activeList.innerHTML = labels
    .map(
      (l) => html`<li>
        <span class="person-swatch" style="background:${l.color}"></span>
        ${l.name}<span class="person-meta">${l.emotion || ""}</span>
      </li>`
    )
    .join("");
}
