/** Display formatting shared by the transport readout and the Ask panel. */

/** Seconds as m:ss.s -- the precision the frame-level data warrants. */
export function formatTime(seconds) {
  if (!isFinite(seconds)) return "0:00.0";
  const m = Math.floor(seconds / 60);
  const s = (seconds % 60).toFixed(1).padStart(4, "0");
  return `${m}:${s}`;
}

/** The non-time columns of an agent result row, as one readable line. */
export function formatMeta(meta) {
  return Object.entries(meta)
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([k, v]) => `${k}: ${typeof v === "number" ? Math.round(v * 1000) / 1000 : v}`)
    .join(" · ");
}
