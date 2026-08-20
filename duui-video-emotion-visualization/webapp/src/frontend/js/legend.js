/**
 * The two match-confidence legends in the sidebar, as disclosures.
 *
 * Both person panels name their score column with a small header, and
 * the fuller explanation of what the number actually measures used to
 * live in a `title` on it. That put the only written description of the
 * score somewhere a keyboard cannot reach, a screen reader announces
 * inconsistently, and a touch screen never shows -- so the header is a
 * button now, and the text is a real paragraph it toggles.
 *
 * Generic over both legends rather than wired per panel: they are the
 * same control saying different things, and each one already names the
 * paragraph it owns through aria-controls.
 */

export function initLegendDisclosures() {
  for (const toggle of document.querySelectorAll(".person-legend-toggle")) {
    const help = document.getElementById(toggle.getAttribute("aria-controls"));
    if (!help) continue;

    toggle.addEventListener("click", () => {
      const open = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", open ? "false" : "true");
      help.hidden = open;
    });
  }
}
