// Flat config, CommonJS on purpose.
//
// The tooling's node_modules lives in the lint image at /opt/tooling, not beside
// this file -- the source is mounted read-only so that no checker can rewrite
// what it is checking. An ESM `import` here would be resolved by Node relative
// to this file and fail; `require` honours NODE_PATH, which the image sets.
const js = require("@eslint/js");

module.exports = [
  {
    ignores: ["docs/legacy/**", "node_modules/**", "webapp/src/frontend/fonts/**"],
  },
  {
    files: ["**/*.js"],
    languageOptions: {
      ecmaVersion: 2024,
      sourceType: "module",
      globals: {
        // Listed rather than pulled from a globals package, so that an
        // unexpected global is an error instead of something a broad preset
        // quietly allowed. The frontend runs in a browser and nowhere else.
        window: "readonly",
        document: "readonly",
        console: "readonly",
        fetch: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
        setInterval: "readonly",
        clearInterval: "readonly",
        requestAnimationFrame: "readonly",
        cancelAnimationFrame: "readonly",
        localStorage: "readonly",
        location: "readonly",
        navigator: "readonly",
        URL: "readonly",
        Image: "readonly",
        IntersectionObserver: "readonly",
        ResizeObserver: "readonly",
        MutationObserver: "readonly",
        AbortController: "readonly",
        getComputedStyle: "readonly",
        Event: "readonly",
        CustomEvent: "readonly",
        KeyboardEvent: "readonly",
        Response: "readonly",
      },
    },
    rules: js.configs.recommended.rules,
  },
  {
    // Written to be pasted into a browser console, and to drop into
    // Playwright's evaluate() unchanged if a headless toolchain is ever added.
    // Its trailing `module.exports` guard is what makes that possible, so
    // `module` is legitimately referenced here and nowhere else.
    files: ["webapp/tests/a11y_browser_check.js"],
    languageOptions: { globals: { module: "writable" } },
  },
];
