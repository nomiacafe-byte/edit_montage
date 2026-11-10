from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
import subprocess
import time
import uuid
import urllib.request
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

ROOT = Path(os.getenv("RAFA_WORK_DIR", "/tmp/rafa-studio"))
ROOT.mkdir(parents=True, exist_ok=True)
MAX_FILE_BYTES = int(os.getenv("RAFA_MAX_FILE_BYTES", str(1024 * 1024 * 1024)))
MAX_PROJECT_BYTES = int(os.getenv("RAFA_MAX_PROJECT_BYTES", str(5 * 1024 * 1024 * 1024)))
PROJECT_TTL = int(os.getenv("RAFA_PROJECT_TTL_SECONDS", str(6 * 60 * 60)))
API_TOKEN = os.getenv("RAFA_API_TOKEN", "")
ACCESS_PASSWORD = os.getenv("RAFA_ACCESS_PASSWORD", "")
SESSION_SECRET = os.getenv("RAFA_SESSION_SECRET", "")
CORS_ORIGINS = [x.strip() for x in os.getenv("RAFA_CORS_ORIGINS", "*").split(",") if x.strip()]

app = FastAPI(title="Rafa Studio Render API", version="0.1.1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS != ["*"] else ["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Rafa-Token"],
)

jobs: dict[str, dict[str, Any]] = {}
project_locks: dict[str, asyncio.Lock] = {}
creation_events: dict[str, list[float]] = {}


def issue_session() -> str:
    expires = str(int(time.time()) + 43200)
    signature = hmac.new(SESSION_SECRET.encode(), expires.encode(), hashlib.sha256).hexdigest()
    return expires + "." + signature


def valid_session(token: str | None) -> bool:
    if not token or not SESSION_SECRET:
        return False
    try:
        expires, signature = token.split(".", 1)
        if int(expires) < int(time.time()):
            return False
        expected = hmac.new(SESSION_SECRET.encode(), expires.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
    except (ValueError, TypeError):
        return False


def guard(token: str | None) -> None:
    if API_TOKEN and hmac.compare_digest(token or "", API_TOKEN):
        return
    if ACCESS_PASSWORD and valid_session(token):
        return
    if not API_TOKEN and not ACCESS_PASSWORD:
        raise HTTPException(status_code=503, detail="Configure backend access before accepting uploads")
    raise HTTPException(status_code=401, detail="Session expired or access denied")

def project_dir(project_id: str) -> Path:
    if not project_id.isalnum():
        raise HTTPException(status_code=400, detail="Invalid project id")
    path = ROOT / project_id
    if not path.exists():
        raise HTTPException(status_code=404, detail="Project not found or expired")
    return path


def save_state(project_id: str) -> None:
    folder = ROOT / project_id
    state = jobs.get(project_id)
    if state:
        (folder / "job.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def load_state(project_id: str) -> dict[str, Any]:
    if project_id in jobs:
        return jobs[project_id]
    file = project_dir(project_id) / "job.json"
    if not file.exists():
        raise HTTPException(status_code=404, detail="Job not found")
    state = json.loads(file.read_text(encoding="utf-8"))
    jobs[project_id] = state
    return state


def enforce_creation_limit(ip: str) -> None:
    now = time.time()
    events = [t for t in creation_events.get(ip, []) if now - t < 3600]
    active = sum(
        1 for state in jobs.values()
        if state.get("owner_ip") == ip and state.get("status") not in ("error", "downloading")
    )
    if len(events) >= 5 or active >= 2:
        raise HTTPException(status_code=429, detail="Trop de projets actifs. Réessaie plus tard.")
    events.append(now)
    creation_events[ip] = events


def run_cmd(args: list[str], timeout: int = 3600) -> str:
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
    if proc.returncode:
        raise RuntimeError((proc.stderr or proc.stdout)[-5000:])
    return proc.stdout


def probe(path: Path) -> dict[str, Any]:
    raw = run_cmd([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:format_tags=creation_time:stream=codec_type,width,height,r_frame_rate:stream_tags=creation_time",
        "-of", "json", str(path)
    ], timeout=120)
    data = json.loads(raw)
    streams = data.get("streams", [])
    fmt = data.get("format", {})
    tags = fmt.get("tags", {}) or {}
    if not tags.get("creation_time"):
        tags = next((stream.get("tags", {}) for stream in streams if (stream.get("tags", {}) or {}).get("creation_time")), tags)
    return {
        "duration": max(0.0, float(fmt.get("duration", 0) or 0)),
        "has_audio": any(s.get("codec_type") == "audio" for s in streams),
        "width": next((s.get("width") for s in streams if s.get("codec_type") == "video"), None),
        "height": next((s.get("height") for s in streams if s.get("codec_type") == "video"), None),
        "creation_time": tags.get("creation_time"),
    }


def frame_metrics(path: Path, duration: float) -> list[dict[str, float]]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return []
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    real_duration = duration or (total / fps if fps else 0)
    if real_duration <= 0:
        cap.release()
        return []
    # Sample at a moderate interval: enough to find strong moments without decoding every frame.
    step = max(1.0, real_duration / 120.0)
    samples: list[dict[str, float]] = []
    t = 0.25
    previous: np.ndarray | None = None
    while t < real_duration - 0.1:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if ok and frame is not None:
            small = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
            brightness = float(np.mean(gray)) / 255.0
            sharpness = min(float(cv2.Laplacian(gray, cv2.CV_64F).var()) / 500.0, 1.0)
            saturation = float(np.mean(hsv[:, :, 1])) / 255.0
            motion = 0.0 if previous is None else min(float(cv2.absdiff(gray, previous).mean()) / 45.0, 1.0)
            # Penalize near-black/overexposed frames; reward detail and moderate visual energy.
            exposure = max(0.0, 1.0 - abs(brightness - 0.52) / 0.55)
            quality = 0.48 * sharpness + 0.28 * exposure + 0.12 * saturation + 0.12 * motion
            samples.append({
                "time": float(t), "brightness": brightness, "sharpness": sharpness,
                "saturation": saturation, "motion": motion, "score": quality
            })
            previous = gray
        t += step
    cap.release()
    return samples


def vision_describe_candidates(candidates: list[dict[str, Any]]) -> bool:
    """Optional semantic shot understanding. Sends sampled still frames, never source video files."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return False
    model = os.getenv("RAFA_VISION_MODEL", "gpt-5.5")
    ranked = sorted(candidates, key=lambda c: c["visual_score"], reverse=True)[:40]
    for offset in range(0, len(ranked), 8):
        batch = ranked[offset:offset + 8]
        content: list[dict[str, Any]] = [{
            "type": "input_text",
            "text": (
                "You classify sampled still frames for Rafa Pizza, a premium mobile pizza catering brand. "
                "Return only JSON with an items array. Each item must include index, category, quality, action, light, notes. "
                "category must be one of dough, topping, guests, oven, finished_pizza, other. "
                "quality is an integer 1-5 for clarity, composition and usefulness. "
                "light is day, dusk, night, indoor or unknown. Describe only what is visible; never infer an unseen action. "
                "Use guests only when people are clearly visible and finished_pizza only for a complete appetizing pizza."
            )
        }]
        for local_index, candidate in enumerate(batch):
            cap = cv2.VideoCapture(candidate["path"])
            cap.set(cv2.CAP_PROP_POS_MSEC, float(candidate["moment_time"]) * 1000)
            ok, frame = cap.read()
            cap.release()
            if not ok or frame is None:
                continue
            h, w = frame.shape[:2]
            scale = min(1.0, 640 / max(w, h))
            if scale < 1.0:
                frame = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 72])
            if not ok:
                continue
            data_url = "data:image/jpeg;base64," + base64.b64encode(encoded.tobytes()).decode("ascii")
            content.append({"type": "input_text", "text": "Frame index " + str(local_index) + "."})
            content.append({"type": "input_image", "image_url": data_url, "detail": "low"})
        if len(content) == 1:
            continue
        payload = json.dumps({
            "model": model,
            "store": False,
            "max_output_tokens": 1800,
            "input": [{"role": "user", "content": content}],
        }).encode("utf-8")
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=payload,
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = json.loads(response.read().decode("utf-8"))
            output_text = "\n".join(
                part.get("text", "")
                for item in body.get("output", []) if item.get("type") == "message"
                for part in item.get("content", []) if part.get("type") == "output_text"
            )
            parsed = json.loads(output_text)
            for result in parsed.get("items", []):
                index = int(result.get("index", -1))
                if index < 0 or index >= len(batch):
                    continue
                candidate = batch[index]
                category = str(result.get("category", "other"))
                if category not in {"dough", "topping", "guests", "oven", "finished_pizza", "other"}:
                    category = "other"
                candidate["semantic_category"] = category
                candidate["semantic_quality"] = max(1, min(5, int(result.get("quality", 3))))
                candidate["semantic_action"] = str(result.get("action", ""))[:180]
                candidate["semantic_light"] = str(result.get("light", "unknown"))
                candidate["semantic_notes"] = str(result.get("notes", ""))[:180]
        except Exception:
            return False
    return any("semantic_category" in candidate for candidate in ranked)


def choose_moments(files: list[dict[str, Any]], target_seconds: float = 26.0) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for source_index, item in enumerate(files):
        path = Path(item["path"])
        meta = probe(path)
        if meta["duration"] < 1.0:
            continue
        samples = frame_metrics(path, meta["duration"])
        if not samples:
            continue

        # Find several separated quality peaks in long recordings.
        peaks = sorted(samples, key=lambda x: x["score"], reverse=True)
        chosen_peaks: list[dict[str, float]] = []
        for sample in peaks:
            if all(abs(sample["time"] - prev["time"]) >= 4.5 for prev in chosen_peaks):
                chosen_peaks.append(sample)
            if len(chosen_peaks) >= 8:
                break

        clip_len = min(4.0, max(2.2, target_seconds / 7.0))
        for peak_index, best in enumerate(chosen_peaks):
            start = max(0.0, min(best["time"] - clip_len * 0.45, meta["duration"] - clip_len))
            actual_len = min(clip_len, meta["duration"] - start)
            if actual_len < 1.2:
                continue
            candidates.append({
                **item, "source_index": source_index, "candidate_index": peak_index,
                "duration": meta["duration"], "has_audio": meta["has_audio"],
                "creation_time": meta["creation_time"], "start": start,
                "end": start + actual_len, "clip_duration": actual_len,
                "brightness": best["brightness"], "visual_score": best["score"],
                "moment_time": best["time"], "analysis_samples": len(samples),
            })

    if not candidates:
        raise RuntimeError("Aucun passage vidéo exploitable n'a été détecté.")

    semantic_enabled = vision_describe_candidates(candidates)

    # Rank by visual quality, but cap each source at seven shots so one long recording can fill a 20–30 s Reel without letting a single angle dominate.
    selected_pool = sorted(candidates, key=lambda c: c["visual_score"] + (0.08 * c.get("semantic_quality", 3) if semantic_enabled else 0.0), reverse=True)
    chosen: list[dict[str, Any]] = []
    source_counts: dict[int, int] = {}
    elapsed = 0.0
    for candidate in selected_pool:
        source_id = int(candidate["source_index"])
        if source_counts.get(source_id, 0) >= 7:
            continue
        if elapsed >= target_seconds:
            break
        remaining = target_seconds - elapsed
        if remaining < 1.5:
            break
        candidate = dict(candidate)
        candidate["clip_duration"] = min(candidate["clip_duration"], remaining)
        candidate["end"] = candidate["start"] + candidate["clip_duration"]
        chosen.append(candidate)
        source_counts[source_id] = source_counts.get(source_id, 0) + 1
        elapsed += candidate["clip_duration"]

    if not chosen:
        chosen = [max(candidates, key=lambda c: c["visual_score"])]

    # Prefer embedded capture time when most selected clips have trustworthy tags.
    dated = [c for c in chosen if c.get("creation_time")]
    chronology_mode = "visual-light-estimate"
    if len(dated) >= max(2, int(len(chosen) * 0.6)):
        # Creation time is often identical for every moment in one long source file;
        # use the actual in-file timecode as the secondary chronological key.
        chosen.sort(key=lambda c: (c.get("creation_time") or "9999", c["moment_time"]))
        chronology_mode = "capture-timestamps"
    elif len({c["source_index"] for c in chosen}) == 1:
        chosen.sort(key=lambda c: c["moment_time"])
        chronology_mode = "single-recording-timecodes"
    else:
        # Low-confidence fallback: reduce obvious night-to-day reversals.
        chosen.sort(key=lambda c: c["brightness"])

    audit = {
        "mode": chronology_mode,
        "selected_count": len(chosen),
        "source_count": len({c["source_index"] for c in chosen}),
        "semantic_analysis": "vision-enabled" if semantic_enabled else "visual-fallback",
        "shot_categories": [c.get("semantic_category", "unclassified") for c in chosen],
        "estimated_seconds": round(sum(c["clip_duration"] for c in chosen), 2),
        "chronology_confidence": "high" if chronology_mode in ("capture-timestamps", "single-recording-timecodes") else "low",
        "note": "Plusieurs moments distincts sont évalués par vidéo, avec au plus sept extraits par source pour gérer aussi un seul long enregistrement. L'ordre par luminosité est une estimation, pas une preuve de chronologie; les événements distincts devront être regroupés par analyse sémantique.",
    }
    return chosen, audit


def render_video(folder: Path, selected: list[dict[str, Any]]) -> Path:
    segments: list[Path] = []
    for index, item in enumerate(selected):
        source = Path(item["path"])
        segment = folder / f"segment_{index:03d}.mp4"
        vf = "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1,fps=30,format=yuv420p"
        cmd = [
            "ffmpeg", "-y", "-ss", f'{item["start"]:.3f}', "-i", str(source),
            "-t", f'{item["clip_duration"]:.3f}',
        ]
        if not item["has_audio"]:
            cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
        cmd += ["-map", "0:v:0", "-map", "0:a:0?" if item["has_audio"] else "1:a:0",
                "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
                "-shortest", "-movflags", "+faststart", str(segment)]
        run_cmd(cmd, timeout=1800)
        segments.append(segment)

    concat_file = folder / "concat.txt"
    concat_file.write_text("".join(f"file '{p.name}'\n" for p in segments), encoding="utf-8")
    output = folder / "preview.mp4"
    run_cmd([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-c", "copy", "-movflags", "+faststart", str(output)
    ], timeout=1800)
    for segment in segments:
        segment.unlink(missing_ok=True)
    concat_file.unlink(missing_ok=True)
    return output


async def process_project(project_id: str) -> None:
    folder = ROOT / project_id
    state = jobs[project_id]
    try:
        state.update(status="analyzing", progress=8, message="Inspection des vidéos et de leurs métadonnées.")
        save_state(project_id)
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        files = manifest["files"]
        selected, audit = await asyncio.to_thread(choose_moments, files)
        state.update(status="rendering", progress=48, message="Sélection des meilleurs passages et assemblage vertical.", audit=audit,
                     selected=[{k: v for k, v in c.items() if k not in ("path",)} for c in selected])
        save_state(project_id)
        output = await asyncio.to_thread(render_video, folder, selected)
        state.update(status="preview_ready", progress=100, message="Aperçu prêt. Vérifie le montage avant de télécharger.", preview="/api/projects/"+project_id+"/preview")
        state["output_path"] = str(output)
        state["sources_ready_for_cleanup"] = True
        save_state(project_id)
    except Exception as exc:
        state.update(status="error", progress=0, message="Le montage n'a pas pu être généré.", error=str(exc)[-1800:])
        save_state(project_id)


class ProjectCreate(BaseModel):
    filenames: list[str] = Field(min_length=1, max_length=1000)


class FileComplete(BaseModel):
    filename: str
    size: int = Field(gt=0)
    chunks: int = Field(gt=0, le=10000)


class CompleteProject(BaseModel):
    files: list[FileComplete] = Field(min_length=1, max_length=1000)


class LoginPayload(BaseModel):
    password: str = Field(min_length=1, max_length=256)


@app.post("/api/auth/login")
def login(payload: LoginPayload, request: Request):
    if not ACCESS_PASSWORD or not SESSION_SECRET:
        raise HTTPException(status_code=503, detail="Backend access password is not configured")
    ip = request.client.host if request.client else "unknown"
    key = "login:" + ip
    now = time.time()
    attempts = [stamp for stamp in creation_events.get(key, []) if now - stamp < 900]
    if len(attempts) >= 10:
        raise HTTPException(status_code=429, detail="Too many login attempts")
    attempts.append(now)
    creation_events[key] = attempts
    if not hmac.compare_digest(payload.password, ACCESS_PASSWORD):
        raise HTTPException(status_code=401, detail="Mot de passe incorrect")
    creation_events.pop(key, None)
    return {"token": issue_session(), "expires_in": 43200}

@app.get("/health")
def health():
    return {"ok": True, "service": "rafa-studio-render", "version": "0.1.0"}


@app.post("/api/projects")
def create_project(payload: ProjectCreate, request: Request, x_rafa_token: str | None = Header(default=None)):
    guard(x_rafa_token)
    client_ip = request.client.host if request.client else "unknown"
    enforce_creation_limit(client_ip)
    project_id = uuid.uuid4().hex
    folder = ROOT / project_id
    (folder / "chunks").mkdir(parents=True)
    now = time.time()
    state = {"project_id": project_id, "status": "uploading", "progress": 0,
             "message": "Projet créé. Téléverse les vidéos.", "created_at": now,
             "updated_at": now, "filenames": payload.filenames, "owner_ip": client_ip}
    jobs[project_id] = state
    save_state(project_id)
    return {"project_id": project_id, "chunk_size_hint": 8 * 1024 * 1024}


@app.put("/api/projects/{project_id}/files/{file_id}/chunks/{chunk_index}")
async def upload_chunk(project_id: str, file_id: str, chunk_index: int, file: UploadFile = File(...),
                       x_rafa_token: str | None = Header(default=None)):
    guard(x_rafa_token)
    folder = project_dir(project_id)
    if not file_id.startswith("f") or not file_id[1:].isdigit() or len(file_id) != 5 or chunk_index < 0 or chunk_index >= 128:
        raise HTTPException(status_code=400, detail="Invalid file or chunk id")
    data = await file.read(8 * 1024 * 1024 + 1)
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Chunk exceeds 8 MB")
    chunk_dir = folder / "chunks" / file_id
    chunk_dir.mkdir(parents=True, exist_ok=True)
    chunk_path = chunk_dir / f"{chunk_index:06d}.part"
    current_bytes = sum(p.stat().st_size for p in folder.rglob("*.part"))
    previous_size = chunk_path.stat().st_size if chunk_path.exists() else 0
    if current_bytes - previous_size + len(data) > MAX_PROJECT_BYTES:
        raise HTTPException(status_code=413, detail="Project exceeds total size limit")
    chunk_path.write_bytes(data)
    state = load_state(project_id)
    state["updated_at"] = time.time()
    save_state(project_id)
    return {"ok": True, "chunk": chunk_index, "bytes": len(data)}


@app.post("/api/projects/{project_id}/complete")
async def complete_project(project_id: str, payload: CompleteProject,
                           x_rafa_token: str | None = Header(default=None)):
    guard(x_rafa_token)
    folder = project_dir(project_id)
    lock = project_locks.setdefault(project_id, asyncio.Lock())
    async with lock:
        state = load_state(project_id)
        if state["status"] not in ("uploading", "uploaded"):
            raise HTTPException(status_code=409, detail="Project is already processing")
        manifest_files = []
        total = 0
        for index, item in enumerate(payload.files):
            if item.size > MAX_FILE_BYTES:
                raise HTTPException(status_code=413, detail=f"{item.filename} exceeds file size limit")
            file_id = f"f{index:04d}"
            chunks = folder / "chunks" / file_id
            parts = sorted(chunks.glob("*.part")) if chunks.exists() else []
            if len(parts) != item.chunks:
                raise HTTPException(status_code=400, detail=f"Missing chunks for {item.filename}")
            target = folder / f"source_{index:04d}{Path(item.filename).suffix.lower()}"
            with target.open("wb") as out:
                for part in parts:
                    with part.open("rb") as src:
                        shutil.copyfileobj(src, out)
            if target.stat().st_size != item.size:
                target.unlink(missing_ok=True)
                raise HTTPException(status_code=400, detail=f"Size mismatch for {item.filename}")
            total += item.size
            if total > MAX_PROJECT_BYTES:
                raise HTTPException(status_code=413, detail="Project exceeds total size limit")
            manifest_files.append({"name": item.filename, "path": str(target)})
            shutil.rmtree(chunks, ignore_errors=True)
        shutil.rmtree(folder / "chunks", ignore_errors=True)
        (folder / "manifest.json").write_text(json.dumps({"files": manifest_files}, ensure_ascii=False), encoding="utf-8")
        state.update(status="queued", progress=2, message="Téléversement terminé. Analyse en attente.", updated_at=time.time())
        save_state(project_id)
        asyncio.create_task(process_project(project_id))
    return {"ok": True, "project_id": project_id, "status": "queued"}


@app.get("/api/projects/{project_id}")
def project_status(project_id: str, x_rafa_token: str | None = Header(default=None)):
    guard(x_rafa_token)
    state = load_state(project_id)
    safe = {k: v for k, v in state.items() if k != "output_path"}
    return safe


@app.get("/api/projects/{project_id}/preview")
def preview(project_id: str, x_rafa_token: str | None = Header(default=None)):
    guard(x_rafa_token)
    state = load_state(project_id)
    path = state.get("output_path")
    if state.get("status") != "preview_ready" or not path or not Path(path).exists():
        raise HTTPException(status_code=409, detail="Preview is not ready")
    return FileResponse(path, media_type="video/mp4", filename="rafa-studio-preview.mp4")


@app.get("/api/projects/{project_id}/download")
def download(project_id: str, x_rafa_token: str | None = Header(default=None)):
    guard(x_rafa_token)
    state = load_state(project_id)
    path = state.get("output_path")
    if state.get("status") not in ("preview_ready", "downloading", "download_ready") or not path or not Path(path).exists():
        raise HTTPException(status_code=409, detail="Final MP4 is not ready")
    state.update(status="download_ready", message="MP4 transmis. Confirmation de livraison en attente.")
    save_state(project_id)
    return FileResponse(path, media_type="video/mp4", filename="Rafa-Pizza-Reel.mp4")


@app.post("/api/projects/{project_id}/ack-download")
def acknowledge_download(project_id: str, x_rafa_token: str | None = Header(default=None)):
    guard(x_rafa_token)
    state = load_state(project_id)
    if state.get("status") != "download_ready":
        raise HTTPException(status_code=409, detail="No completed MP4 delivery to acknowledge")
    folder = project_dir(project_id)
    shutil.rmtree(folder, ignore_errors=True)
    jobs.pop(project_id, None)
    project_locks.pop(project_id, None)
    return {"ok": True, "deleted": True}


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str, x_rafa_token: str | None = Header(default=None)):
    guard(x_rafa_token)
    folder = project_dir(project_id)
    shutil.rmtree(folder, ignore_errors=True)
    jobs.pop(project_id, None)
    project_locks.pop(project_id, None)
    return {"ok": True, "deleted": True}


def purge_expired_once() -> None:
    now = time.time()
    for folder in ROOT.iterdir():
        if not folder.is_dir():
            continue
        try:
            state_file = folder / "job.json"
            state = jobs.get(folder.name)
            created = state.get("created_at") if state else None
            if created is None:
                created = json.loads(state_file.read_text()).get("created_at", folder.stat().st_mtime) if state_file.exists() else folder.stat().st_mtime
            if now - float(created) > PROJECT_TTL:
                shutil.rmtree(folder, ignore_errors=True)
                jobs.pop(folder.name, None)
                project_locks.pop(folder.name, None)
        except Exception:
            continue


async def expiry_sweeper() -> None:
    while True:
        await asyncio.to_thread(purge_expired_once)
        await asyncio.sleep(900)


@app.on_event("startup")
async def start_expiry_sweeper():
    await asyncio.to_thread(purge_expired_once)
    asyncio.create_task(expiry_sweeper())
