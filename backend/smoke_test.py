import os
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:8080"
sample = ROOT / "rafa-smoke.mp4"
env = os.environ.copy()
env.pop("RAFA_ACCESS_PASSWORD", None)
env.pop("RAFA_API_TOKEN", None)
env.pop("RAFA_SESSION_SECRET", None)
server = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8080"],
    cwd=ROOT,
    env=env,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)


def run(*args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


try:
    for _ in range(60):
        try:
            if requests.get(BASE + "/health", timeout=2).ok:
                break
        except requests.RequestException:
            time.sleep(1)
    else:
        raise RuntimeError("API did not become healthy")

    run("ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x480:rate=25",
        "-t", "7", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(sample))

    created = requests.post(BASE + "/api/projects", json={"filenames": [sample.name]}, timeout=20)
    created.raise_for_status()
    project_id = created.json()["project_id"]

    data = sample.read_bytes()
    uploaded = requests.put(
        f"{BASE}/api/projects/{project_id}/files/f0000/chunks/0",
        files={"file": (sample.name + ".part", data, "application/octet-stream")},
        timeout=60,
    )
    uploaded.raise_for_status()

    complete = requests.post(
        f"{BASE}/api/projects/{project_id}/complete",
        json={"files": [{"filename": sample.name, "size": len(data), "chunks": 1}]},
        timeout=20,
    )
    complete.raise_for_status()

    state = None
    for _ in range(180):
        response = requests.get(f"{BASE}/api/projects/{project_id}", timeout=20)
        response.raise_for_status()
        state = response.json()
        if state["status"] in ("preview_ready", "error"):
            break
        time.sleep(1)
    if not state or state["status"] != "preview_ready":
        raise RuntimeError("Render failed: " + str(state))

    preview = requests.get(f"{BASE}/api/projects/{project_id}/preview", timeout=60)
    preview.raise_for_status()
    assert len(preview.content) > 1000 and preview.content[4:8] == b"ftyp"

    final = requests.get(f"{BASE}/api/projects/{project_id}/download", timeout=60)
    final.raise_for_status()
    assert len(final.content) > 1000 and final.content[4:8] == b"ftyp"

    ack = requests.post(f"{BASE}/api/projects/{project_id}/ack-download", timeout=20)
    ack.raise_for_status()
    deleted = requests.get(f"{BASE}/api/projects/{project_id}", timeout=20)
    assert deleted.status_code == 404

    print("Smoke test passed: upload -> analyze -> FFmpeg MP4 -> preview -> download -> cleanup")
finally:
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
    sample.unlink(missing_ok=True)
