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
import { compareNames, personColorFor, personName, state } from "../state.js";

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
    // Alphabetical by video filename, matching the People panel's
    // person-name sort applied to `rows` below.
    others.sort((a, b) => compareNames(a.video_filename, b.video_filename));
    rows.push({ person, others, cluster });
  }

  if (!rows.length) {
    el.crossVideoPanel.style.display = "none";
    el.crossVideoList.innerHTML = "";
    return;
  }
  rows.sort((a, b) => compareNames(personName(a.person), personName(b.person)));

  el.crossVideoPanel.style.display = "";
  el.crossVideoList.innerHTML = rows
    .map(({ person, others, cluster }) => {
      const name = personName(person);
      // One element per appearance rather than a comma-joined string --
      // the filenames are long enough that a run-on line was hard to
      // read. html`` passes an array of nested results through as-is.
      // Each entry carries its own cross-video match distance (the
      // global-identity job's cosine distance for *that* person), shown
      // at the end of the entry with a tooltip.
      const otherList = others.map((o) => {
        const od = o.global_person_match_score;
        const odText = od != null ? Number(od).toFixed(2) : "";
        const odTitle =
          od != null
            ? `Cross-video match confidence: ${odText} -- cosine distance (0 = identical, 2 = opposite) between this person's embedding centroid and their nearest lookalike in another video, from the global-identity job. Lower is a more confident match; this is not the import pipeline's confidence score.`
            : "";
        return html`<span class="cross-video"
          >${o.video_filename} (${o.clip_label || "person " + o.person_id})${odText != ""
            ? html`<span class="cross-video-distance" title="${odTitle}">${odText}</span>`
            : ""}</span
        >`;
      });
      // The name is wrapped, unlike in the two single-line person
      // lists: these rows are a grid (see .cross-list in sidebar.css)
      // and the video list below needs an element to align under.
      const gpId = cluster && cluster.global_person_id;
      const gpName = cluster && cluster.real_name;
      return html`<li>
        <span class="person-swatch" style="background:${personColorFor(person.person_id)}"></span>
        <span class="person-name">${name}${gpId != null
          ? html`<span class="person-global-id">(global #${gpId}${gpName ? ` · ${gpName}` : ""})</span>`
          : ""}</span>
        <span class="person-meta">${otherList}</span>
      </li>`;
    })
    .join("");
}
