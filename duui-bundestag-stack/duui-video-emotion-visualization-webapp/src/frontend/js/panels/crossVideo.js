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
import { personColorFor, personName, state } from "../state.js";

/**
 * Whether a cluster member is this video's person.
 *
 * Both halves of the key: person_id comes from each CAS's own
 * annotation numbering, so "person 1" exists in most videos in the
 * corpus. This is the one place in the frontend where people from
 * *different* videos are compared -- everywhere else a payload is a
 * single video, where person_id alone is unambiguous.
 */
function isSamePerson(member, person, videoId) {
  return member.person_id === person.person_id && member.video_id === videoId;
}

export function renderCrossVideoPanel(data) {
  const clusters = state.globalPersonClusters || [];
  const videoId = data.video.video_id;
  const rows = [];
  for (const person of data.persons) {
    const cluster = clusters.find((c) =>
      c.members.some((m) => isSamePerson(m, person, videoId))
    );
    if (!cluster) continue;
    const others = cluster.members.filter((m) => !isSamePerson(m, person, videoId));
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
      const name = personName(person);
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
