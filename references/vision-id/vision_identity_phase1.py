"""
Phase-1 Vision-Identity — reine Python-Pipeline (Skeleton).

Ablauf (jeder Schritt ist genau eine Funktion):
    [1] ShotSegmenter   PySceneDetect            -> Shot[]
    [2] VisionIdentity  YOLO+ByteTrack(Reset@Shot) -> PersonTrack[], PersonDetection[]
                        InsightFace(SCRFD+ArcFace) -> FaceDetection[] (+ Embedding, Track-Zuordnung)
    [3] Clustering      Agglomerative (cosine)    -> FaceIdentity[] (setzt PersonTrack.face)

Output = die 5 Dataclasses unten. Sie spiegeln das Phase-1-Subset des
MultimodalIdentityTypeSystem; FK = Python-Objektreferenz (CAS-Mapping später trivial).

Install:
    pip install scenedetect[opencv] ultralytics insightface onnxruntime opencv-python scikit-learn numpy
    # Linux+NVIDIA: onnxruntime-gpu statt onnxruntime

    ersetzt mit uv . siehe .toml

MModellgewichte – Größen (dein Lauf):

YOLO11n (yolo11n.pt)              5.4 MB    -> Projektordner
InsightFace buffalo_l            ~280 MB   -> ~/.insightface/models/buffalo_l/
  det_10g.onnx        SCRFD-Detektor
  w600k_r50.onnx      ArcFace-Embedding (das größte, ResNet50)
  2d106det.onnx       2D-Landmarks
  1k3d68.onnx         3D-Landmarks
  genderage.onnx      Alter/Geschlecht
  (die letzten drei nutzt die Pipeline nicht aktiv, kommen aber im Pack mit)

Gewichte gesamt: ~285 MB (einmalig, dann gecacht)

Zusätzlich – nicht "Gewichte", aber Plattenplatz:
  .venv (alle Pakete inkl. torch)  ~3–5 GB
  uv-Cache (~/.cache/uv)           kann über Projekte hinweg wachsen
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import os
import cv2
import numpy as np
import json



# ============================================================
#  CONFIG — Parameter pro Pipeline-Schritt
# ============================================================
@dataclass
class ShotConfig:
    threshold: float = 27.0  # PySceneDetect ContentDetector: höher = weniger Schnitte
    min_scene_len: int = 15  # min. Shot-Länge in Frames


@dataclass
class DetectTrackConfig:
    model: str = "yolo11n.pt"  # alt: yolo26n.pt / yolov8n.pt
    person_class_id: int = 0  # COCO: 0 = person
    conf: float = 0.35  # Detektor-Konfidenz
    imgsz: int = 640
    tracker_yaml: str = "bytetrack.yaml"
    reset_per_shot: bool = True  # Tracker an jeder Shot-Grenze zurücksetzen


@dataclass
class FaceConfig:
    model_pack: str = "buffalo_l"  # SCRFD + ArcFace gebündelt
    det_size: int = 640
    min_face_frac: float = 0.04  # Gesichtshöhe / Framehöhe -> filtert Publikum/Plenum weg
    min_det_score: float = 0.6


@dataclass
class EmbedConfig:
    samples_per_track: int = 5  # nur die N frontalsten Crops je Track mitteln


@dataclass
class ClusterConfig:
    distance_threshold: float = 0.50  # cosine-Distanz; KLEINER = strenger = mehr Identitäten
    linkage: str = "average"


@dataclass
class PipelineConfig:
    device: str = "auto"  # auto | cuda | mps | cpu
    frame_stride: int = 1  # >1 = jeden n-ten Frame (schneller, lockerer)
    overlay_dir: Optional[str] = None  # gesetzt -> bbox-Overlays als JPGs (visuelle Prüfung)
    shot: ShotConfig = field(default_factory=ShotConfig)
    dettrack: DetectTrackConfig = field(default_factory=DetectTrackConfig)
    face: FaceConfig = field(default_factory=FaceConfig)
    embed: EmbedConfig = field(default_factory=EmbedConfig)
    cluster: ClusterConfig = field(default_factory=ClusterConfig)


# ============================================================
#  DATENMODELL — Phase-1-Subset (FK = Objektreferenz)
# ============================================================
@dataclass
class Shot:
    shot_index: int
    start_frame: int
    end_frame: int
    time_start: float
    time_end: float


@dataclass
class FaceIdentity:  # TOP, clip-konstant
    face_id: str
    embedding: Optional[np.ndarray] = None
    person: None = None  # Phase 1: immer null


@dataclass
class PersonTrack:  # ein Lauf EINER Person in EINEM Shot
    track_id: int  # Tracker-ID (shot-lokal!)
    shot: Shot  # FK
    face: Optional[FaceIdentity] = None  # FK, wird vom Clustering gesetzt
    _embeds: list = field(default_factory=list)  # intern: [(frontality, normed_emb)]


@dataclass
class PersonDetection:  # eine Körper-Box je Frame
    frame_index: int
    x: float;
    y: float;
    width: float;
    height: float  # normiert 0..1
    detection_score: float
    time_start: float
    track: PersonTrack  # FK


@dataclass
class FaceDetection:  # eine Gesichts-Box je Frame
    frame_index: int
    x: float;
    y: float;
    width: float;
    height: float
    detection_score: float
    time_start: float
    track: PersonTrack  # FK


# ============================================================
#  Helfer
# ============================================================
def _pick_device(prefer: str) -> str:
    if prefer != "auto":
        return prefer
    import torch
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _frontality(kps: np.ndarray) -> float:
    """0..1 aus 5 SCRFD-Landmarks: wie zentriert die Nase zwischen den Augen liegt."""
    eye_cx = (kps[0, 0] + kps[1, 0]) / 2
    eye_dist = abs(kps[1, 0] - kps[0, 0]) + 1e-6
    return float(max(0.0, 1.0 - abs(kps[2, 0] - eye_cx) / eye_dist))


def _contains(pbox, fcx, fcy) -> bool:
    x1, y1, x2, y2 = pbox
    return x1 <= fcx <= x2 and y1 <= fcy <= y2


# ============================================================
#  [1] ShotSegmenter
# ============================================================
def segment_shots(video_path: str, cfg: ShotConfig) -> list[Shot]:
    from scenedetect import detect, ContentDetector
    scenes = detect(video_path, ContentDetector(threshold=cfg.threshold,
                                                min_scene_len=cfg.min_scene_len))
    return [Shot(i, s.frame_num, e.frame_num, s.seconds, e.seconds)
            for i, (s, e) in enumerate(scenes)]


# ============================================================
#  [2] VisionIdentity — ein Video-Durchlauf, Sub-Schritte 2a/2b
# ============================================================
def analyze_video(video_path: str, shots: list[Shot], cfg: PipelineConfig):
    from ultralytics import YOLO
    from insightface.app import FaceAnalysis

    device = _pick_device(cfg.device)
    # YOLO
    yolo = YOLO(cfg.dettrack.model)
    # InsightFace (CPU/CoreML auf mac; CUDA auf Server)
    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if device == "cuda" \
        else ["CPUExecutionProvider"]
    face_app = FaceAnalysis(name=cfg.face.model_pack, providers=providers)
    face_app.prepare(ctx_id=0 if device == "cuda" else -1,
                     det_size=(cfg.face.det_size, cfg.face.det_size))

    def shot_of(fi: int) -> Optional[Shot]:
        for sh in shots:
            if sh.start_frame <= fi < sh.end_frame:
                return sh
        return None

    def reset_tracker():
        try:
            for t in yolo.predictor.trackers:
                t.reset()
        except Exception:
            pass  # predictor existiert erst nach erstem track()-Call

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0  # für Fortschrittsanzeige
    if cfg.overlay_dir:
        os.makedirs(cfg.overlay_dir, exist_ok=True)

    tracks: dict[tuple[int, int], PersonTrack] = {}  # (shot_index, track_id) -> PersonTrack
    person_dets: list[PersonDetection] = []
    face_dets: list[FaceDetection] = []
    cur_shot: Optional[Shot] = None
    fi = -1

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        fi += 1
        if fi % cfg.frame_stride:
            continue
        if total and fi % max(1, total // 50) == 0:  # ~alle 2 %
            done = len(tracks)
            print(f"\r    Frame {fi}/{total}  ({100 * fi // total}%)  "
                  f"{done} Tracks", end="", flush=True)
        sh = shot_of(fi)
        if sh is None:
            continue
        if sh is not cur_shot:
            if cfg.dettrack.reset_per_shot:
                reset_tracker()  # Reset @Shot-Grenze
            cur_shot = sh
        t = fi / fps

        # --- 2a) YOLO-Detektion + ByteTrack -> PersonTrack / PersonDetection ---
        res = yolo.track(frame, persist=True, classes=[cfg.dettrack.person_class_id],
                         conf=cfg.dettrack.conf, imgsz=cfg.dettrack.imgsz,
                         tracker=cfg.dettrack.tracker_yaml, device=device, verbose=False)[0]
        frame_persons = []  # [(pbox_px, PersonTrack)] für die Gesichts-Zuordnung
        if res.boxes is not None and res.boxes.id is not None:
            for box, tid, score in zip(res.boxes.xyxy.cpu().numpy(),
                                       res.boxes.id.cpu().numpy().astype(int),
                                       res.boxes.conf.cpu().numpy()):
                key = (sh.shot_index, int(tid))  # track_id ist shot-lokal
                pt = tracks.setdefault(key, PersonTrack(track_id=int(tid), shot=sh))
                x1, y1, x2, y2 = box
                person_dets.append(PersonDetection(
                    fi, x1 / W, y1 / H, (x2 - x1) / W, (y2 - y1) / H,
                    float(score), t, pt))
                frame_persons.append((box, pt))

        # --- 2b) InsightFace -> Filter -> Track-Zuordnung -> FaceDetection + Embedding ---
        for f in face_app.get(frame):
            x1, y1, x2, y2 = f.bbox
            if (y2 - y1) / H < cfg.face.min_face_frac or f.det_score < cfg.face.min_det_score:
                continue  # Publikum/Plenum/Low-Score raus
            fcx, fcy = (x1 + x2) / 2, (y1 + y2) / 2
            host = next((pt for pbox, pt in frame_persons if _contains(pbox, fcx, fcy)), None)
            if host is None:
                continue  # kein passender Personen-Track
            face_dets.append(FaceDetection(
                fi, x1 / W, y1 / H, (x2 - x1) / W, (y2 - y1) / H,
                float(f.det_score), t, host))
            host._embeds.append((_frontality(f.kps), f.normed_embedding))

    cap.release()
    print()  # Zeilenumbruch nach der \r-Fortschrittszeile
    return list(tracks.values()), person_dets, face_dets


def render_overlays(video_path: str, result: dict, out_dir: str):
    """Zweiter Durchlauf NACH dem Clustering: zeichnet Shot, Track-ID und
    Gesamt-ID (FaceIdentity) ins Bild. Nur Frames mit Detektionen werden geschrieben."""
    from collections import defaultdict
    os.makedirs(out_dir, exist_ok=True)
    pd_by_frame, fd_by_frame = defaultdict(list), defaultdict(list)
    for d in result["person_detections"]:
        pd_by_frame[d.frame_index].append(d)
    for d in result["face_detections"]:
        fd_by_frame[d.frame_index].append(d)

    cap = cv2.VideoCapture(video_path)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fi = -1
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        fi += 1
        if fi not in pd_by_frame and fi not in fd_by_frame:
            continue
        # Personen-Boxen: Shot, Track-ID (shot-lokal), Gesamt-ID (clip-weit)
        for d in pd_by_frame.get(fi, []):
            x1, y1 = int(d.x * W), int(d.y * H)
            x2, y2 = int((d.x + d.width) * W), int((d.y + d.height) * H)
            pid = d.track.face.face_id.replace("face_", "P") if d.track.face else "—"
            label = f"S{d.track.shot.shot_index} t{d.track.track_id} {pid}"
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, label, (x1, max(14, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
        # Gesichts-Boxen (blau)
        for d in fd_by_frame.get(fi, []):
            x1, y1 = int(d.x * W), int(d.y * H)
            cv2.rectangle(frame, (x1, y1),
                          (x1 + int(d.width * W), y1 + int(d.height * H)), (255, 0, 0), 2)
        cv2.imwrite(os.path.join(out_dir, f"{fi:06d}.jpg"), frame)
    cap.release()


# ============================================================
#  [3] Clustering -> FaceIdentity (setzt PersonTrack.face)
# ============================================================
def cluster_identities(tracks: list[PersonTrack], emb_cfg: EmbedConfig,
                       cfg: ClusterConfig) -> list[FaceIdentity]:
    from sklearn.cluster import AgglomerativeClustering

    # ein Repräsentativ-Embedding je Track (Mittel der frontalsten Crops)
    usable, vecs = [], []
    for pt in tracks:
        if not pt._embeds:
            continue
        top = sorted(pt._embeds, key=lambda e: e[0], reverse=True)[:emb_cfg.samples_per_track]
        v = np.mean([e[1] for e in top], axis=0)
        v /= (np.linalg.norm(v) + 1e-9)
        usable.append(pt);
        vecs.append(v)

    if not usable:
        return []
    X = np.vstack(vecs)
    if len(usable) == 1:
        labels = np.array([0])
    else:
        labels = AgglomerativeClustering(
            n_clusters=None, distance_threshold=cfg.distance_threshold,
            metric="cosine", linkage=cfg.linkage).fit_predict(X)

    identities: dict[int, FaceIdentity] = {}
    for pt, v, lbl in zip(usable, vecs, labels):
        fid = identities.setdefault(int(lbl),
                                    FaceIdentity(face_id=f"face_{int(lbl)}", embedding=v))
        pt.face = fid  # FK PersonTrack -> FaceIdentity
    return list(identities.values())


# ============================================================
#  Orchestrierung
# ============================================================
def run(video_path: str, cfg: PipelineConfig = PipelineConfig()):
    print(f"[1] ShotSegmenter …")
    shots = segment_shots(video_path, cfg.shot)
    print(f"    -> {len(shots)} Shots")

    print(f"[2] VisionIdentity (device={_pick_device(cfg.device)}) …")
    tracks, pdets, fdets = analyze_video(video_path, shots, cfg)
    print(f"    -> {len(tracks)} Tracks, {len(pdets)} PersonDetections, {len(fdets)} FaceDetections")

    print(f"[3] Clustering …")
    identities = cluster_identities(tracks, cfg.embed, cfg.cluster)
    print(f"    -> {len(identities)} FaceIdentities")

    result = {
        "shots": shots,
        "tracks": tracks,
        "person_detections": pdets,
        "face_detections": fdets,
        "identities": identities
    }

    fps = cv2.VideoCapture(video_path).get(cv2.CAP_PROP_FPS) or 25.0

    export_phase1_json(
        video_path,
        result,
        fps,
        "phase1.json"
    )


    if cfg.overlay_dir:
        print(f"[4] Overlays -> {cfg.overlay_dir}/ …")
        render_overlays(video_path, result, cfg.overlay_dir)

    return result
##neu
def export_phase1_json(video_path: str, result: dict, fps: float, out_path: str):
    shots = result["shots"]
    tracks = result["tracks"]
    fdets = result["face_detections"]
    identities = result["identities"]

    # FaceIdentity mapping
    face_map = {f.face_id: f for f in identities}

    # Tracks -> JSON
    tracks_json = []
    for t in tracks:
        tracks_json.append({
            "id": f"s{t.shot.shot_index}_t{t.track_id}",
            "track_id": t.track_id,
            "shot": f"shot_{t.shot.shot_index}",
            "face": t.face.face_id if t.face else None
        })

    # FaceDetections -> JSON
    fd_json = []
    for i, d in enumerate(fdets):
        fd_json.append({
            "id": f"fd_{i:06d}",
            "frame_index": d.frame_index,
            "x": d.x,
            "y": d.y,
            "width": d.width,
            "height": d.height,
            "det_score": d.detection_score,
            "time_start": d.frame_index / fps,
            "track": f"s{d.track.shot.shot_index}_t{d.track.track_id}"
        })

    # FaceIdentities -> JSON
    fi_json = []
    for f in identities:
        fi_json.append({
            "id": f.face_id,
            "face_id": f.face_id,
            "person": None
        })

    payload = {
        "video": {
            "path": video_path,
            "width": None,
            "height": None,
            "fps": fps
        },
        "face_identities": fi_json,
        "tracks": tracks_json,
        "face_detections": fd_json
    }

    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)


if __name__ == "__main__":
    import sys

    cfg = PipelineConfig()
    cfg.frame_stride = 5
    cfg.overlay_dir = "overlay" # zum visuellen Prüfen; auf None für reinen Lauf
    out = run(sys.argv[1] if len(sys.argv) > 1 else "clip.mp4", cfg)

