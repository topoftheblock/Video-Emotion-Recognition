"""
Phase-1 Emotion-Komponente — standalone, rein Python, kein CAS.

Liest den Phase-1-Graph (JSON, nur Koordinaten + FKs), schneidet die Gesichts-Crops
bei Bedarf aus dem Video, laesst HSEmotion (enet_b0_8_va_mtl) drueberlaufen und schreibt
emotions.json. Das ist der Datenmodell-Test fuer den Emotion-Typ:

    Frame-Ebene   : ein Emotion je FaceDetection   (granularity="frame",   reference=FaceDetection)
    Segment-Ebene : ein Emotion je PersonTrack      (granularity="segment", reference=PersonTrack,
                                                      aggregated_from=[Frame-Emotionen])

HSEmotion enet_b0_8_va_mtl liefert pro Crop 10 Werte:
    scores[:8]  = 8 AffectNet-Klassen (Anger, Contempt, Disgust, Fear, Happiness,
                  Neutral, Sadness, Surprise)   -> Verteilung
    scores[-2]  = Valence   (-1..1)
    scores[-1]  = Arousal   (-1..1)
Dominance gibt es nicht (AffectNet = VA, nicht VAD) -> bleibt null.

Install:
    uv add hsemotion-onnx onnxruntime opencv-python numpy
    # Server+NVIDIA: onnxruntime-gpu statt onnxruntime

Lauf:
    python emotion.py phase1.json            # -> emotions.json


benötigter json input:
{
  "video":            { "path": "clip.mp4", "width": 1920, "height": 1080, "fps": 25.0 },
  "face_identities":  [ { "id": "face_0", "face_id": "face_0", "person": null } ],
  "tracks":           [ { "id": "s0_t3", "track_id": 3, "shot": "shot_0", "face": "face_0" } ],
  "face_detections":  [ { "id": "fd_000123", "frame_index": 123,
                          "x": 0.41, "y": 0.22, "width": 0.07, "height": 0.12,
                          "det_score": 0.94, "time_start": 4.92, "track": "s0_t3" } ]
}
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional
from collections import defaultdict
import json
import sys
import cv2
import numpy as np
import urllib.request  # ensures submodule is loaded

# ============================================================
#  CONFIG
# ============================================================
@dataclass
class EmotionConfig:
    model_name: str = "enet_b0_8_va_mtl"  # einziges Modell der Familie mit V/A
    device: str = "auto"                  # auto | cpu | cuda | coreml
    crop_margin: float = 0.20             # Rand um die SCRFD-Box (FER-Netze brauchen Stirn/Kinn)
    batch_per_frame: bool = True          # alle Gesichter eines Frames auf einmal inferieren
    aggregate_segments: bool = True       # Track-Aggregat (granularity="segment") erzeugen
    out_path: str = "emotions.json"


# ============================================================
#  DATENMODELL — Emotion-Subset (FK = String-ID, wie im Input-JSON)
# ============================================================
@dataclass
class EmotionScore:
    label: str
    score: float


@dataclass
class Emotion:
    id: str
    reference_type: str            # "FaceDetection" | "PersonTrack"
    reference: str                 # FK-ID
    granularity: str               # "frame" | "segment"
    modality: str                  # "video"
    scores: list                   # list[EmotionScore]
    dominant: str
    dominant_score: float
    time_start: float
    time_end: float
    frame_index: Optional[int] = None
    valence: Optional[float] = None
    arousal: Optional[float] = None
    dominance: Optional[float] = None      # immer null in Phase 1
    aggregated_from: list = field(default_factory=list)   # list[str] (Emotion-IDs)
    model: Optional[str] = None


# ============================================================
#  HSEmotion laden (+ optional Provider tauschen fuer GPU)
# ============================================================
def _resolve_providers(device: str) -> Optional[list[str]]:
    import onnxruntime as ort
    avail = set(ort.get_available_providers())
    if device == "cpu":
        return ["CPUExecutionProvider"]
    if device == "cuda":
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    if device == "coreml":
        return ["CoreMLExecutionProvider", "CPUExecutionProvider"]
    # auto: nimm das beste verfuegbare
    if "CUDAExecutionProvider" in avail:
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    if "CoreMLExecutionProvider" in avail:
        return ["CoreMLExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


def load_recognizer(cfg: EmotionConfig):
    from hsemotion_onnx.facial_emotions import HSEmotionRecognizer, get_model_path
    fer = HSEmotionRecognizer(model_name=cfg.model_name)
    providers = _resolve_providers(cfg.device)
    if providers != ["CPUExecutionProvider"]:
        # der Wrapper pinnt CPU -> Session mit gewuenschten Providern neu anlegen
        import onnxruntime as ort
        fer.ort_session = ort.InferenceSession(get_model_path(cfg.model_name), providers=providers)
    print(f"    HSEmotion {cfg.model_name} @ {fer.ort_session.get_providers()[0]}")
    return fer


# ============================================================
#  Helfer
# ============================================================
def _load_input(path: str):
    data = json.load(open(path))
    vid = data["video"]
    dets = data["face_detections"]
    tracks = {t["id"]: t for t in data.get("tracks", [])}
    faces = {f["id"]: f for f in data.get("face_identities", [])}
    return vid, dets, tracks, faces


def _crop(frame, det, W, H, margin) -> Optional[np.ndarray]:
    """Crop in RGB mit Rand; None falls degeneriert/ausserhalb."""
    x1, y1 = det["x"] * W, det["y"] * H
    bw, bh = det["width"] * W, det["height"] * H
    mx, my = margin * bw, margin * bh
    x1, y1 = int(max(0, x1 - mx)), int(max(0, y1 - my))
    x2, y2 = int(min(W, x1 + bw + 2 * mx)), int(min(H, y1 + bh + 2 * my))
    if x2 - x1 < 8 or y2 - y1 < 8:
        return None
    return cv2.cvtColor(frame[y1:y2, x1:x2], cv2.COLOR_BGR2RGB)


def _to_scores(vec8: np.ndarray, labels: dict) -> tuple[list, str, float]:
    """8er-Vektor -> EmotionScore-Liste + dominant/dominantScore."""
    scores = [EmotionScore(labels[i], float(vec8[i])) for i in range(len(vec8))]
    k = int(np.argmax(vec8))
    return scores, labels[k], float(vec8[k])


# ============================================================
#  Frame-Ebene: ein Emotion je FaceDetection
# ============================================================
def emotions_per_frame(video_path, dets, fer, cfg) -> list[Emotion]:
    by_frame: dict[int, list] = defaultdict(list)
    for d in dets:
        by_frame[d["frame_index"]].append(d)
    needed = set(by_frame)
    labels = fer.idx_to_class

    cap = cv2.VideoCapture(video_path)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out: list[Emotion] = []
    fi, done = -1, 0
    total = len(needed)

    while needed:
        ok, frame = cap.read()
        if not ok:
            break
        fi += 1
        if fi not in by_frame:
            continue
        needed.discard(fi)
        done += 1
        if done % 25 == 0 or not needed:
            print(f"\r    Frame {done}/{total}  ({len(out)} Frame-Emotionen)", end="", flush=True)

        crops, owners = [], []
        for d in by_frame[fi]:
            c = _crop(frame, d, W, H, cfg.crop_margin)
            if c is not None:
                crops.append(c); owners.append(d)
        if not crops:
            continue

        if cfg.batch_per_frame and len(crops) > 1:
            _, raw = fer.predict_multi_emotions(crops, logits=False)   # (N, 10)
        else:
            raw = np.vstack([fer.predict_emotions(c, logits=False)[1] for c in crops])

        for d, row in zip(owners, raw):
            sc, dom, dom_s = _to_scores(row[:8], labels)
            out.append(Emotion(
                id=f"emo_{d['id']}", reference_type="FaceDetection", reference=d["id"],
                granularity="frame", modality="video",
                scores=sc, dominant=dom, dominant_score=dom_s,
                time_start=d["time_start"], time_end=d["time_start"],
                frame_index=d["frame_index"],
                valence=float(row[-2]), arousal=float(row[-1]), dominance=None,
                model=cfg.model_name))
    cap.release()
    print()
    return out


# ============================================================
#  Segment-Ebene: ein Emotion je PersonTrack (Mittel der Frame-Emotionen)
# ============================================================
def emotions_per_track(frame_emos, dets, tracks, fer, cfg) -> list[Emotion]:
    det_track = {d["id"]: d["track"] for d in dets}      # FaceDetection-ID -> Track-ID
    labels = fer.idx_to_class
    groups: dict[str, list] = defaultdict(list)
    for e in frame_emos:
        tid = det_track.get(e.reference)
        if tid is not None:
            groups[tid].append(e)

    out: list[Emotion] = []
    for tid, emos in groups.items():
        mat = np.array([[s.score for s in e.scores] for e in emos])    # (n, 8)
        mean = mat.mean(axis=0)
        sc, dom, dom_s = _to_scores(mean, labels)
        vals = [e.valence for e in emos if e.valence is not None]
        aros = [e.arousal for e in emos if e.arousal is not None]
        out.append(Emotion(
            id=f"emo_seg_{tid}", reference_type="PersonTrack", reference=tid,
            granularity="segment", modality="video",
            scores=sc, dominant=dom, dominant_score=dom_s,
            time_start=min(e.time_start for e in emos),
            time_end=max(e.time_end for e in emos),
            frame_index=None,
            valence=float(np.mean(vals)) if vals else None,
            arousal=float(np.mean(aros)) if aros else None,
            dominance=None,
            aggregated_from=[e.id for e in emos],
            model=f"{cfg.model_name} (mean/{len(emos)})"))
    return out


# ============================================================
#  Serialisierung + Zusammenfassung
# ============================================================
def _emo_to_dict(e: Emotion) -> dict:
    d = asdict(e)
    d["scores"] = [{"label": s["label"], "score": round(s["score"], 4)} for s in d["scores"]]
    for k in ("dominant_score", "valence", "arousal"):
        if d[k] is not None:
            d[k] = round(d[k], 4)
    return d


def _summary(segment_emos, tracks, faces):
    """Konsolen-Rollup je FaceIdentity -> hilft beim Augenschein, NICHT im JSON."""
    if not segment_emos or not tracks:
        return
    by_face = defaultdict(list)
    for e in segment_emos:
        t = tracks.get(e.reference)
        face = t.get("face") if t else None
        by_face[face].append(e)
    print("\n    Identitaet   Tracks  dominant (haeufigste)   ~valence")
    for face, emos in by_face.items():
        doms = defaultdict(int)
        for e in emos:
            doms[e.dominant] += 1
        top = max(doms, key=doms.get)
        v = np.mean([e.valence for e in emos if e.valence is not None]) if emos else 0.0
        print(f"    {str(face):<12} {len(emos):>5}   {top:<20}   {v:+.2f}")


# ============================================================
#  Orchestrierung
# ============================================================
def run(input_json: str, cfg: EmotionConfig = EmotionConfig()):
    print(f"[*] lade {input_json}")
    vid, dets, tracks, faces = _load_input(input_json)
    print(f"    {len(dets)} FaceDetections, {len(tracks)} Tracks, {len(faces)} FaceIdentities")

    print("[*] HSEmotion laden")
    fer = load_recognizer(cfg)

    print("[1] Frame-Emotionen")
    frame_emos = emotions_per_frame(vid["path"], dets, fer, cfg)
    print(f"    -> {len(frame_emos)}")

    segment_emos = []
    if cfg.aggregate_segments and tracks:
        print("[2] Segment-Aggregate (je Track)")
        segment_emos = emotions_per_track(frame_emos, dets, tracks, fer, cfg)
        print(f"    -> {len(segment_emos)}")

    all_emos = frame_emos + segment_emos
    json.dump({
        "source": input_json,
        "model": cfg.model_name,
        "emotions": [_emo_to_dict(e) for e in all_emos],
    }, open(cfg.out_path, "w"), indent=2, ensure_ascii=False)
    print(f"[*] geschrieben: {cfg.out_path}  ({len(all_emos)} Emotion-Objekte)")

    _summary(segment_emos, tracks, faces)
    return all_emos


if __name__ == "__main__":
    cfg = EmotionConfig()
    run(sys.argv[1] if len(sys.argv) > 1 else "phase1.json", cfg)


# [1] Frame-Emotionen
#     Frame 1555/1555  (1979 Frame-Emotionen)
#     -> 1983
# [2] Segment-Aggregate (je Track)
#     -> 48
# [*] geschrieben: emotions.json  (2031 Emotion-Objekte)
#
#     Identitaet   Tracks  dominant (haeufigste)   ~valence
#     face_8           2   Sadness                -0.34
#     face_15          1   Neutral                +0.05
#     face_10          2   Neutral                +0.21
#     face_20          1   Neutral                +0.17
#     face_19          1   Neutral                -0.22
#     face_5           2   Neutral                +0.12
#     face_21          1   Neutral                +0.06
#     face_13          3   Neutral                +0.19
#     face_2           8   Neutral                -0.16
#     face_24          1   Surprise               +0.20
#     face_1           2   Neutral                +0.15
#     face_0           2   Neutral                +0.14
#     face_3           3   Neutral                +0.12
#     face_26          1   Neutral                +0.18
#     face_16          1   Neutral                +0.21
#     face_4           2   Neutral                +0.23
#     face_6           2   Neutral                +0.19
#     face_14          1   Neutral                +0.26
#     face_18          1   Neutral                +0.23
#     face_17          1   Neutral                +0.10
#     face_11          2   Neutral                +0.14
#     face_23          1   Neutral                +0.11
#     face_25          1   Neutral                +0.18
#     face_12          2   Neutral                +0.16
#     face_27          1   Neutral                +0.19
#     face_22          1   Fear                   +0.17
#     face_7           1   Neutral                +0.15
#     face_9           1   Surprise               +0.19
