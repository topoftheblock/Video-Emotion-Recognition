/**
 * The browser half of the accessibility checks: axe over five
 * application states, plus the keyboard sweep.
 *
 * Phase 6.3 of docs/accessibility.md. The other half --
 * contrast_check.py and cvd_check.py -- are pure functions over
 * committed values and run under pytest with no browser. These cannot:
 * three of the five states only exist after JS has run, and the tab
 * order is a property of the rendered document.
 *
 * There is no headless-browser toolchain in this repo (it is Python end
 * to end), so this is written to be pasted into a browser console
 * rather than to require one. It returns a plain object, so it also
 * drops straight into Playwright/Puppeteer `evaluate()` if that ever
 * gets added -- see the note at the bottom.
 *
 *   1. docker compose up -d db webapp
 *   2. open http://localhost:8010, size the window to desktop
 *   3. paste this file into the console, then:  await a11yCheck()
 *
 * Compare the result against docs/a11y-verification.md.
 */

async function a11yCheck({ axeUrl = "https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js" } = {}) {
  const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"];
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  if (!window.axe) {
    const s = document.createElement("script");
    s.src = axeUrl;
    await new Promise((res, rej) => { s.onload = res; s.onerror = rej; document.head.appendChild(s); });
    await wait(500);
  }

  const run = async (state) => {
    const r = await window.axe.run(document, { runOnly: { type: "tag", values: TAGS } });
    return {
      state,
      violations: r.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length })),
      // Two rules are expected here in every state and are not findings:
      // video-caption (the out-of-scope subtitle track) and color-contrast
      // (axe declines to resolve backgrounds behind pseudo-elements and
      // overlaps). See docs/a11y-verification.md.
      incomplete: [...new Set(r.incomplete.map((v) => v.id))],
    };
  };

  /* The Ask agent needs DUUI_QUERY_API_KEY, which a dev stack usually
     has no value for. Only the agent's *response* is stubbed -- the form
     submit, renderAskResults() and every element axe then scans are the
     real code path. */
  const realFetch = window.fetch.bind(window);
  const stub = (payload) => {
    window.fetch = (input, init) => {
      const url = typeof input === "string" ? input : input.url;
      if (url.includes("/api/ask")) {
        return Promise.resolve(new Response(JSON.stringify(payload), {
          status: 200, headers: { "Content-Type": "application/json" },
        }));
      }
      return realFetch(input, init);
    };
  };
  const ask = async (question) => {
    document.querySelector("#askInput").value = question;
    document.querySelector("#askForm").dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
    await wait(1700);
  };

  const results = { viewport: window.innerWidth };
  results.A = await run("A-default");

  document.querySelector("#personList .person-row")?.click();
  await wait(450);
  results.B = await run("B-person-filter");

  stub({
    columns: ["video_id", "start_time", "end_time", "emotion"],
    rows: [
      { video_id: 4, start_time: 12.5, end_time: 15, emotion: "happiness" },
      { video_id: 4, start_time: 31.2, end_time: 34.8, emotion: "anger" },
    ],
    row_count: 2, truncated: false, sql: "SELECT ...",
    explanation: "Two moments.", overlays: ["boxes"],
    segments: [
      { video_id: 4, start_time: 12.5, end_time: 15, meta: { emotion: "happiness" } },
      { video_id: 4, start_time: 31.2, end_time: 34.8, meta: { emotion: "anger" } },
    ],
  });
  await ask("where is someone happy?");
  results.C = await run("C-ask-segments");
  // Phase 1.1: these rows are <button>s, so they must be reachable.
  results.C.focusableInResults = document.querySelectorAll("#askResults button").length;

  stub({
    columns: ["filename", "person_count"],
    rows: [{ filename: "a.mp4", person_count: 3 }, { filename: "b.mp4", person_count: 5 }],
    row_count: 2, truncated: true, sql: "SELECT ...",
    explanation: "Counts.", overlays: [], segments: [],
  });
  await ask("how many people per video?");
  results.D = await run("D-ask-table");

  const input = document.querySelector("#videoComboInput");
  input.focus();
  input.dispatchEvent(new Event("focus", { bubbles: true }));
  await wait(300);
  input.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
  input.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
  await wait(300);
  results.E = await run("E-combobox-open");
  // Phase 1.5: aria-expanded belongs on the input, options need ids, and
  // the highlight has to be announced through aria-activedescendant.
  results.E.combobox = {
    inputExpanded: input.getAttribute("aria-expanded"),
    activeDescendant: input.getAttribute("aria-activedescendant"),
    optionsWithId: document.querySelectorAll("#videoComboList li[id]").length,
    ariaSelected: document.querySelectorAll('#videoComboList li[aria-selected="true"]').length,
  };

  window.fetch = realFetch;
  results.keyboardSweep = a11ySweep();
  results.summary = {
    totalViolations: ["A", "B", "C", "D", "E"].reduce((n, k) => n + results[k].violations.length, 0),
    tabStops: results.keyboardSweep.stops,
    unnamedStops: results.keyboardSweep.unnamed,
  };
  return results;
}

/**
 * The tab order, with each stop's accessible name and state.
 *
 * Focusable elements in document order. That is the real tab order only
 * while nothing carries a positive tabindex, which is asserted below --
 * and it was checked against twelve actual Tab presses when this was
 * first written. Reload to a clean state before calling.
 */
function a11ySweep() {
  const SELECTOR = [
    "a[href]", "button", "input", "select", "textarea",
    '[tabindex]:not([tabindex="-1"])', "video[controls]", "[contenteditable]",
  ].join(", ");

  const visible = (n) => {
    if (n.disabled || n.hidden) return false;
    const style = getComputedStyle(n);
    return style.display !== "none" && style.visibility !== "hidden" && n.getClientRects().length > 0;
  };

  const nodes = [...document.querySelectorAll(SELECTOR)].filter(visible);
  const usingAxe = Boolean(window.axe);
  if (usingAxe) window.axe.setup(document.documentElement);

  const rows = nodes.map((n, i) => {
    let name = "(axe not loaded)";
    if (usingAxe) {
      try {
        name = window.axe.commons.text
          .accessibleTextVirtual(window.axe.utils.getNodeFromTree(n))
          .replace(/\s+/g, " ").trim();
      } catch (e) { name = "(accname failed)"; }
    }
    const attr = (a) => (n.getAttribute(a) !== null ? `${a.replace("aria-", "")}=${n.getAttribute(a)}` : null);
    return {
      stop: i + 1,
      region: n.closest("header") ? "header"
        : n.closest(".ask-panel") ? "ask"
        : n.closest(".stage") ? "stage"
        : n.closest(".sidebar") ? "sidebar" : "page",
      el: n.tagName.toLowerCase() + (n.id ? `#${n.id}` : "")
        + (typeof n.className === "string" && n.className.trim() ? `.${n.className.trim().split(/\s+/)[0]}` : ""),
      name,
      state: ["aria-pressed", "aria-expanded", "aria-valuetext", "aria-disabled"]
        .map(attr).filter(Boolean).join(" ") || "-",
    };
  });

  if (usingAxe) window.axe.teardown();

  return {
    stops: rows.length,
    unnamed: rows.filter((r) => !r.name || r.name.startsWith("(")).length,
    positiveTabindex: document.querySelectorAll('[tabindex]:not([tabindex="-1"]):not([tabindex="0"])').length,
    headingOutline: [...document.querySelectorAll("h1,h2,h3,h4,h5,h6")].map((h) => h.tagName).join(" "),
    rows,
  };
}

/* If a headless runner is ever added, the whole thing is one call:
 *
 *   await page.addScriptTag({ path: "tests/a11y_browser_check.js" });
 *   const r = await page.evaluate(() => a11yCheck());
 *   expect(r.summary.totalViolations).toBe(0);
 *   expect(r.summary.unnamedStops).toBe(0);
 *
 * That is deliberately not wired up here: it would mean adding a
 * JavaScript toolchain and a browser download to a repo that has neither,
 * which is a bigger decision than this file should make on its own. */
if (typeof module !== "undefined") module.exports = { a11yCheck, a11ySweep };
