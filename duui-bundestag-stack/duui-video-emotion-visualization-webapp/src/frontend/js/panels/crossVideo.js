/**
 * "Also appears in": for each person in this video, every *other*
 * video that
 * duui-video-emotion-global-identity/src/identity/linking.py
 * linked them to.
 *
 * Reads state.globalPersonClusters, fetched once at startup and
 * filtered client-side -- cross-video identity doesn't change between
 * video loads. The panel hides itself entirely when this video has no
 * one who appears elsewhere, which is still the common case: importing
 * videos does not compute these links, so until the global-identity
 * job has been run there are none at all.
 */

import { el, html } from "../dom.js";
import { personColorFor, state } from "../state.js";

export function renderCrossVideoPanel(data) {
  const clusters = state.globalPersonClusters || [];
  const rows = [];
  for (const person of data.persons) {
    const cluster = clusters.find((c) =>
      c.members.some((m) => m.person_id === person.person_id)
    );
    if (!cluster) continue;
    const others = cluster.members.filter((m) => m.person_id !== person.person_id);
    if (!others.length) continue;
    rows.push({ person, others });
  }

  if (!rows.length) {
    el.crossVideoPanel.style.display = "none";
    el.crossVideoList.innerHTML = "";
    return;
  }

  el.crossVideoPanel.style.display = "";
  el.crossVideoList.innerHTML = rows
    .map(({ person, others }) => {
      const name = person.clip_label || `person ${person.person_id}`;
      const otherList = others
        .map((o) => `${o.video_filename} (${o.clip_label || "person " + o.person_id})`)
        .join(", ");
      return html`<li>
        <span class="person-swatch" style="background:${personColorFor(person.person_id)}"></span>
        ${name}<span class="person-meta">${otherList}</span>
      </li>`;
    })
    .join("");
}
