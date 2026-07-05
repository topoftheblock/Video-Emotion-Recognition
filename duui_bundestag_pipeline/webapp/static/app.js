/**
 * DUUI video review frontend.
 *
 * Everything here is driven off `video.currentTime`: on every
 * timeupdate (and every animation frame while playing, for smoother
 * box tracking) we find whichever rows from the API payload cover
 * the current instant and render them -- subtitle text, the current
 * dominant text-emotion badge, the audio "voice" readout, and
 * bounding boxes for every face/person detection near this time.
 */

const PERSON_COLORS = ["#49d3c8", "#e0a458", "#c77dff", "#7dd3fc", "#f472b6", "#a3e635"];

const state = {
  data: null,
  personColor: new Map(),
  rafHandle: null,
};

const el = {
  videoSelect: document.getElementById("videoSelect"),
  player: document.getElementById("player"),
  overlay: document.getElementById("overlay"),
  stageFrame: document.getElementById("stageFrame"),
  subtitleText: document.getElementById("subtitleText"),
  subtitleEmotion: document.getElementById("subtitleEmotion"),
  playBtn: document.getElementById("playBtn"),
  scrub: document.getElementById("scrub"),
  timeCurrent: document.getElementById("timeCurrent"),
  timeTotal: document.getElementById("timeTotal"),
  voiceLabel: document.getElementById("voiceLabel"),
  valenceFill: document.getElementById("valenceFill"),
  arousalFill: document.getElementById("arousalFill"),
  personList: document.getElementById("personList"),
  activeList: document.getElementById("activeList"),
};

const ctx = el.overlay.getContext("2d");

// ---------------- Bootstrap ----------------

async function loadVideoList() {
  const videos = await fetch("/api/videos").then((r) => r.json());
  el.videoSelect.innerHTML = videos
    .map((v) => `<option value="${v.video_id}">${v.filename} (#${v.video_id})</option>`)
    .join("");
  if (videos.length) {
    await loadVideo(videos[0].video_id);
  }
}

async function loadVideo(videoId) {
  const data = await fetch(`/api/videos/${videoId}/data`).then((r) => r.json());
  state.data = data;
  assignPersonColors(data.persons);
  renderPersonList(data.persons);

  el.player.src = `/media/${encodeURIComponent(data.video.filename)}`;
  el.player.load();
}

function assignPersonColors(persons) {
  state.personColor.clear();
  persons.forEach((p, i) => {
    state.personColor.set(p.person_id, PERSON_COLORS[i % PERSON_COLORS.length]);
  });
}

function renderPersonList(persons) {
  if (!persons.length) {
    el.personList.innerHTML = '<li class="empty-hint">No identified persons.</li>';
    return;
  }
  el.personList.innerHTML = persons
    .map((p) => {
      const color = state.personColor.get(p.person_id);
      const score = p.match_score != null ? `${Math.round(p.match_score * 100)}%` : "";
      return `<li><span class="person-swatch" style="background:${color}"></span>${p.clip_label || "person " + p.person_id}<span class="person-meta">${score}</span></li>`;
    })
    .join("");
}

// ---------------- Time-synced lookups ----------------

/** Rows whose [start_time, end_time] window covers `t`. */
function coveredBy(rows, t) {
  return rows.filter(
    (r) => r.start_time != null && r.end_time != null && r.start_time <= t && t <= r.end_time
  );
}

/** The row (from a list carrying frame_index/t_time) nearest to `t`,
 * within `tolerance` seconds -- used for detections, which are sampled
 * at discrete frames rather than spanning a range. */
function nearestByTime(rows, t, tolerance) {
  let best = null;
  let bestDelta = Infinity;
  for (const r of rows) {
    if (r.t_time == null) continue;
    const delta = Math.abs(r.t_time - t);
    if (delta < bestDelta) {
      bestDelta = delta;
      best = r;
    }
  }
  return bestDelta <= tolerance ? best : null;
}

// ---------------- Per-frame render ----------------

function render() {
  const data = state.data;
  if (!data) return;
  const t = el.player.currentTime;

  renderSubtitle(data, t);
  renderVoicePanel(data, t);
  renderBoundingBoxes(data, t);
  updateTransport(t);
}

function renderSubtitle(data, t) {
  const sentence = coveredBy(data.sentences, t)[0];
  el.subtitleText.textContent = sentence ? sentence.text : "";

  const textEmotion = coveredBy(data.emotions.text, t)[0];
  el.subtitleEmotion.textContent = textEmotion ? textEmotion.dominant_label || "" : "";
}

function renderVoicePanel(data, t) {
  const audioEmotion = coveredBy(data.emotions.audio, t)[0];
  if (!audioEmotion) {
    el.voiceLabel.textContent = "\u2014";
    setBar(el.valenceFill, 0);
    setBar(el.arousalFill, 0);
    return;
  }
  el.voiceLabel.textContent = audioEmotion.dominant_label || "\u2014";
  setBar(el.valenceFill, audioEmotion.valence || 0);
  setBar(el.arousalFill, audioEmotion.arousal || 0);
}

/** Renders a signed value in [-1, 1] as a bar growing left/right from center. */
function setBar(elFill, value) {
  const clamped = Math.max(-1, Math.min(1, value || 0));
  const pct = Math.abs(clamped) * 50;
  if (clamped >= 0) {
    elFill.style.left = "50%";
    elFill.style.width = pct + "%";
  } else {
    elFill.style.left = 50 - pct + "%";
    elFill.style.width = pct + "%";
  }
}

function renderBoundingBoxes(data, t) {
  syncCanvasSize();
  ctx.clearRect(0, 0, el.overlay.width, el.overlay.height);

  const tolerance = 0.15; // seconds -- detections are sampled per-frame, not continuous
  const faceBox = nearestByTime(data.detections.face, t, tolerance);
  const personBox = nearestByTime(data.detections.person, t, tolerance);
  const activeLabels = [];

  for (const box of [faceBox, personBox]) {
    if (!box) continue;
    const color = state.personColor.get(box.person_id) || "#8b94a3";
    const emotionLabel = findEmotionLabelForFrame(data, box);
    drawBox(box, color, emotionLabel);
    if (box === faceBox) {
      const person = data.persons.find((p) => p.person_id === box.person_id);
      activeLabels.push({
        color,
        name: (person && person.clip_label) || (box.person_id ? `person ${box.person_id}` : "unidentified"),
        emotion: emotionLabel,
      });
    }
  }

  renderActiveList(activeLabels);
}

/** Video-modality BaseEmotion rows don't carry their own bbox -- they
 * share `frame_index` with the detection they were computed from, so
 * that's the join key back to a label for this box. */
function findEmotionLabelForFrame(data, box) {
  const match = data.emotions.video.find(
    (e) => e.person_id === box.person_id && e.frame_index === box.frame_index
  );
  return match ? match.dominant_label : null;
}

function drawBox(box, color, emotionLabel) {
  const w = el.overlay.width;
  const h = el.overlay.height;
  const x = box.x * w;
  const y = box.y * h;
  const bw = box.w * w;
  const bh = box.h * h;

  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.strokeRect(x, y, bw, bh);

  if (emotionLabel) {
    ctx.font = "600 12px 'IBM Plex Mono', monospace";
    const label = emotionLabel.toUpperCase();
    const padding = 5;
    const textWidth = ctx.measureText(label).width;
    const tagY = y - 18 >= 0 ? y - 18 : y + bh + 2;

    ctx.fillStyle = color;
    ctx.fillRect(x, tagY, textWidth + padding * 2, 16);
    ctx.fillStyle = "#0a0c0f";
    ctx.fillText(label, x + padding, tagY + 12);
  }
}

function renderActiveList(labels) {
  if (!labels.length) {
    el.activeList.innerHTML = '<li class="empty-hint">No one detected at this frame.</li>';
    return;
  }
  el.activeList.innerHTML = labels
    .map(
      (l) =>
        `<li><span class="person-swatch" style="background:${l.color}"></span>${l.name}<span class="person-meta">${l.emotion || ""}</span></li>`
    )
    .join("");
}

function syncCanvasSize() {
  const rect = el.stageFrame.getBoundingClientRect();
  if (el.overlay.width !== rect.width || el.overlay.height !== rect.height) {
    el.overlay.width = rect.width;
    el.overlay.height = rect.height;
  }
}

// ---------------- Transport controls ----------------

function formatTime(seconds) {
  if (!isFinite(seconds)) return "0:00.0";
  const m = Math.floor(seconds / 60);
  const s = (seconds % 60).toFixed(1).padStart(4, "0");
  return `${m}:${s}`;
}

function updateTransport(t) {
  el.timeCurrent.textContent = formatTime(t);
  el.timeTotal.textContent = formatTime(el.player.duration || 0);
  if (!el.scrub.matches(":active")) {
    const pct = el.player.duration ? (t / el.player.duration) * 1000 : 0;
    el.scrub.value = pct;
  }
}

function loop() {
  render();
  if (!el.player.paused) {
    state.rafHandle = requestAnimationFrame(loop);
  }
}

// ---------------- Event wiring ----------------

el.videoSelect.addEventListener("change", (e) => loadVideo(Number(e.target.value)));

el.player.addEventListener("loadedmetadata", () => {
  syncCanvasSize();
  render();
});

el.player.addEventListener("play", () => {
  el.playBtn.textContent = "\u23F8";
  cancelAnimationFrame(state.rafHandle);
  loop();
});

el.player.addEventListener("pause", () => {
  el.playBtn.textContent = "\u25B6";
  cancelAnimationFrame(state.rafHandle);
  render();
});

el.player.addEventListener("seeked", render);
el.player.addEventListener("timeupdate", () => {
  if (el.player.paused) render();
});

el.playBtn.addEventListener("click", () => {
  if (el.player.paused) el.player.play();
  else el.player.pause();
});

el.scrub.addEventListener("input", () => {
  if (!el.player.duration) return;
  el.player.currentTime = (el.scrub.value / 1000) * el.player.duration;
});

window.addEventListener("resize", () => {
  syncCanvasSize();
  render();
});

loadVideoList();
