/**
 * The two person lists in the sidebar: everyone the importer identified
 * in this video, and whoever is on screen right now.
 *
 * The first list is also the app's person filter — clicking a row
 * narrows the three emotion panels to that person, clicking it again
 * widens them back out. The selection itself lives in state so the
 * panels can read it; this module owns the list markup and the click.
 */

import { el, html } from "../lib/dom.js";
import { compareNames, personColorFor, personName, state } from "../state.js";

/**
 * Wire the person list once. `onChange` runs after a click has changed
 * state.selectedPersonId, and is what rebuilds the panels that read it
 * — kept as a callback so this module doesn't have to import them.
 */
export function initPersonList(onChange) {
  el.personList.addEventListener("click", (event) => {
    const row = /** @type {HTMLElement} */ (
      /** @type {Element} */ (event.target).closest("[data-person-id]")
    );
    if (!row) return;

    const personId = Number(row.dataset.personId);
    // Clicking the selected person again clears the filter, so the one
    // control both sets and unsets it.
    state.selectedPersonId = state.selectedPersonId === personId ? null : personId;

    renderPersonList(state.data ? state.data.persons : []);
    onChange();
  });
}

export function renderPersonList(persons) {
  // The legend names the column .person-meta renders into; pointless
  // (and, worse, floating over nothing) once that column has no rows
  // under it.
  el.personLegend.style.display = persons.length ? "" : "none";
  // The disclosure it opens goes with it, collapsed — otherwise an
  // explanation left open survives into the next video, floating above
  // a list that may have nothing under it.
  if (!persons.length) {
    el.personLegendHelp.hidden = true;
    el.personLegend
      .querySelector(".person-legend-toggle")
      .setAttribute("aria-expanded", "false");
  }

  if (!persons.length) {
    el.personList.innerHTML = '<li class="empty-hint">No identified persons.</li>';
    return;
  }
  // Alphabetical by display name, not import order.
  const sorted = [...persons].sort((a, b) =>
    compareNames(personName(a), personName(b)),
  );
  el.personList.innerHTML = sorted
    .map((p) => {
      const score =
        p.audio_video_match_score != null
          ? `${Math.round(p.audio_video_match_score * 100)}%`
          : "";
      // Repeats the legend's title on the number itself, so the
      // explanation is reachable by hovering either the column header
      // once or any one row — no need to remember which row you learned
      // it from.
      const scoreTitle =
        p.audio_video_match_score != null
          ? `Face/voice match confidence: ${score} — how sure the import pipeline was that this person's face and voice recordings are the same person.`
          : "";
      // Without this the button's accessible name — computed from its
      // contents — comes out as "person_1100%", which a screen reader
      // reads as "person eleven hundred percent". The number also needs
      // saying what it is: "100%" alone names no quantity.
      const scoreLabel = score ? `match confidence ${score}` : "";
      const selected = state.selectedPersonId === p.person_id;
      return html`<li>
        <button
          type="button"
          class="person-row${selected ? " is-selected" : ""}"
          data-person-id="${p.person_id}"
          aria-pressed="${selected ? "true" : "false"}"
          title="${
            selected
              ? "Show every person's emotions again"
              : "Show only this person's emotions"
          }"
        >
          <span
            class="person-swatch"
            style="background:${personColorFor(p.person_id)}"
          ></span>
          ${personName(p)}
          <span class="person-meta" aria-label="${scoreLabel}" title="${scoreTitle}"
            >${score}</span
          >
        </button>
      </li>`;
    })
    .join("");
}

export function renderActiveList(labels) {
  if (!labels.length) {
    el.activeList.innerHTML =
      '<li class="empty-hint">No one detected at this frame.</li>';
    return;
  }
  // Alphabetical by display name, same as the other two person lists.
  const sorted = [...labels].sort((a, b) => compareNames(a.name, b.name));
  el.activeList.innerHTML = sorted
    .map(
      (l) =>
        html`<li>
          <span class="person-swatch" style="background:${l.color}"></span>
          ${l.name}
          <span class="person-meta">${l.emotion || ""}</span>
        </li>`,
    )
    .join("");
}
