/**
 * The two person lists in the sidebar: everyone the importer
 * identified in this video, and whoever is on screen right now.
 *
 * The first list is also the app's person filter -- clicking a row
 * narrows the three emotion panels to that person, clicking it again
 * widens them back out. The selection itself lives in state so the
 * panels can read it; this module owns the list markup and the click.
 */

import { el, html } from "../dom.js";
import { personColorFor, personName, state } from "../state.js";

/**
 * Wire the person list once. `onChange` runs after a click has
 * changed state.selectedPersonId, and is what rebuilds the panels
 * that read it -- kept as a callback so this module doesn't have to
 * import them.
 */
export function initPersonList(onChange) {
  el.personList.addEventListener("click", (event) => {
    const row = event.target.closest("[data-person-id]");
    if (!row) return;

    const personId = Number(row.dataset.personId);
    // Clicking the selected person again clears the filter, so the
    // one control both sets and unsets it.
    state.selectedPersonId = state.selectedPersonId === personId ? null : personId;

    renderPersonList(state.data ? state.data.persons : []);
    onChange();
  });
}

export function renderPersonList(persons) {
  if (!persons.length) {
    el.personList.innerHTML = '<li class="empty-hint">No identified persons.</li>';
    return;
  }
  el.personList.innerHTML = persons
    .map((p) => {
      const score = p.match_score != null ? `${Math.round(p.match_score * 100)}%` : "";
      const selected = state.selectedPersonId === p.person_id;
      return html`<li>
        <button
          type="button"
          class="person-row${selected ? " is-selected" : ""}"
          data-person-id="${p.person_id}"
          aria-pressed="${selected ? "true" : "false"}"
          title="${selected
            ? "Show every person's emotions again"
            : "Show only this person's emotions"}"
        >
          <span class="person-swatch" style="background:${personColorFor(p.person_id)}"></span>
          ${personName(p)}<span class="person-meta">${score}</span>
        </button>
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
