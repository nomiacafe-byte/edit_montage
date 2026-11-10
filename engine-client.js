(() => {
  const $ = (id) => document.getElementById(id);
  const button = $("generate");
  const panel = $("renderPanel");
  const progress = $("renderProgress");
  const message = $("renderMessage");
  const preview = $("renderPreview");
  const download = $("downloadFinal");
  const audit = $("chronologyAudit");
  const shotAudit = $("shotAudit");
  let outputBlob = null;
  let outputUrl = null;
  let busy = false;

  const setProgress = (value, label) => {
    progress.value = Math.max(0, Math.min(100, value));
    message.textContent = label;
  };
  const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));
  const waitEvent = (target, eventName, timeout = 12000) => new Promise((resolve, reject) => {
    const timer = setTimeout(() => { cleanup(); reject(new Error("La lecture d'une vidéo prend trop de temps. Essaie avec moins de clips ou des fichiers plus courts.")); }, timeout);
    const cleanup = () => { clearTimeout(timer); target.removeEventListener(eventName, done); target.removeEventListener("error", failed); };
    const done = () => { cleanup(); resolve(); };
    const failed = () => { cleanup(); reject(new Error("Un fichier vidéo n'est pas lisible par Safari sur cet iPhone.")); };
    target.addEventListener(eventName, done, { once: true });
    target.addEventListener("error", failed, { once: true });
  });
  async function readyVideo(video, url) {
    if (video.src !== url) {
      video.pause();
      video.src = url;
      video.load();
      await waitEvent(video, "loadedmetadata");
    } else if (video.readyState < 1) {
      await waitEvent(video, "loadedmetadata");
    }
    if (!Number.isFinite(video.duration) || video.duration <= 0) throw new Error("Durée vidéo illisible.");
    return video.duration;
  }
  async function seek(video, time) {
    const target = Math.max(0, Math.min(time, Math.max(0, video.duration - 0.05)));
    if (Math.abs(video.currentTime - target) < 0.08 && video.readyState >= 2) return;
    const event = waitEvent(video, "seeked", 10000);
    video.currentTime = target;
    await event;
    if (video.readyState < 2) await waitEvent(video, "loadeddata", 10000);
  }
  function scoreFrame(ctx, canvas, previous) {
    const w = canvas.width, h = canvas.height;
    const data = ctx.getImageData(0, 0, w, h).data;
    let sum = 0, sumSq = 0, sat = 0, edges = 0, motion = 0, count = 0;
    const step = 4 * 4;
    for (let i = 0; i < data.length; i += step) {
      const r = data[i], g = data[i + 1], b = data[i + 2];
      const y = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      sum += y; sumSq += y * y;
      sat += Math.max(r, g, b) - Math.min(r, g, b);
      if (i + 4 < data.length) {
        const ny = 0.2126 * data[i + 4] + 0.7152 * data[i + 5] + 0.0722 * data[i + 6];
        edges += Math.abs(y - ny);
      }
      if (previous) motion += (Math.abs(r - previous[i]) + Math.abs(g - previous[i + 1]) + Math.abs(b - previous[i + 2])) / 3;
      count++;
    }
    const mean = sum / count;
    const variance = Math.max(0, sumSq / count - mean * mean);
    const exposure = Math.max(0, 1 - Math.abs(mean - 132) / 150);
    const sharpness = Math.min(1, (edges / count) / 42);
    const color = Math.min(1, (sat / count) / 95);
    const movement = previous ? Math.min(1, (motion / count) / 38) : 0.25;
    const contrast = Math.min(1, Math.sqrt(variance) / 75);
    const exposurePenalty = mean < 22 || mean > 240 ? 0.45 : 1;
    return { score: (0.34 * sharpness + 0.24 * exposure + 0.18 * contrast + 0.12 * color + 0.12 * movement) * exposurePenalty, mean };
  }

  async function analyseClips(clips) {
    const candidates = [];
    const probe = document.createElement("video");
    probe.preload = "auto";
    probe.muted = true;
    probe.playsInline = true;
    const sampleBudget = Math.min(220, Math.max(36, clips.length * 3));
    for (let index = 0; index < clips.length; index++) {
      const clip = clips[index];
      setProgress(5 + (index / clips.length) * 35, "Analyse des images · " + (index + 1) + "/" + clips.length + " · " + clip.file.name);
      const duration = await readyVideo(probe, clip.url);
      clip.duration = duration;
      const count = clips.length === 1
        ? Math.min(54, Math.max(12, Math.ceil(duration / 22)))
        : Math.max(2, Math.min(5, Math.floor(sampleBudget / clips.length)));
      const margin = Math.min(0.8, duration * 0.08);
      let previous = null;
      for (let s = 0; s < count; s++) {
        const time = count === 1 ? duration / 2 : margin + (Math.max(0.1, duration - 2 * margin)) * (s / (count - 1));
        try {
          await seek(probe, time);
          const c = document.createElement("canvas");
          c.width = 160; c.height = 284;
          const cx = c.getContext("2d", { willReadFrequently: true });
          const scale = Math.max(c.width / probe.videoWidth, c.height / probe.videoHeight);
          const sw = probe.videoWidth * scale, sh = probe.videoHeight * scale;
          cx.drawImage(probe, (c.width - sw) / 2, (c.height - sh) / 2, sw, sh);
          const pixels = cx.getImageData(0, 0, c.width, c.height).data;
          const measured = scoreFrame(cx, c, previous);
          candidates.push({ clip, clipIndex: index, time, duration, score: measured.score, light: measured.mean, pixels });
          previous = pixels;
        } catch (error) {
          if (s === 0 && !candidates.some(item => item.clip === clip)) throw error;
        }
      }
      await wait(20);
    }
    probe.pause();
    probe.removeAttribute("src");
    probe.load();
    if (!candidates.length) throw new Error("Aucun passage exploitable n'a pu être analysé.");
    return candidates;
  }

  function chooseShots(candidates, clips) {
    const single = clips.length === 1;
    const sorted = [...candidates].sort((a, b) => b.score - a.score);
    const selected = [];
    for (const item of sorted) {
      if (selected.length >= 12) break;
      const same = selected.filter(s => s.clip === item.clip);
      if (single ? same.some(s => Math.abs(s.time - item.time) < 2.8) : same.length >= 1 || same.some(s => Math.abs(s.time - item.time) < 3.5)) continue;
      const shotLength = Math.min(2.2, Math.max(1.1, item.duration - 0.15));
      if (item.duration > shotLength + 0.2 && (item.time < 0.35 || item.time > item.duration - 0.35)) continue;
      selected.push({ ...item, start: Math.max(0, Math.min(item.duration - shotLength, item.time - shotLength * 0.48)), length: shotLength });
    }
    if (selected.length < 6) {
      for (const item of sorted) {
        if (selected.length >= 12) break;
        if (selected.some(s => s.clip === item.clip && Math.abs(s.time - item.time) < 1.7)) continue;
        const shotLength = Math.min(2.2, Math.max(1.1, item.duration - 0.15));
        selected.push({ ...item, start: Math.max(0, Math.min(item.duration - shotLength, item.time - shotLength * 0.48)), length: shotLength });
      }
    }
    selected.sort((a, b) => {
      if (a.clip === b.clip) return a.time - b.time;
      const ta = Number(a.clip.file.lastModified || 0), tb = Number(b.clip.file.lastModified || 0);
      return ta - tb || a.clipIndex - b.clipIndex;
    });
    return selected;
  }

  function drawCover(ctx, video, width, height) {
    const scale = Math.max(width / video.videoWidth, height / video.videoHeight);
    const sw = video.videoWidth * scale, sh = video.videoHeight * scale;
    ctx.fillStyle = "#211d1b";
    ctx.fillRect(0, 0, width, height);
    ctx.drawImage(video, (width - sw) / 2, (height - sh) / 2, sw, sh);
  }

  async function renderShots(shots) {
    if (!window.MediaRecorder || !HTMLCanvasElement.prototype.captureStream) {
      throw new Error("Safari ne permet pas le rendu vidéo local sur cette version. Mets iOS à jour ou ouvre Rafa Studio dans Safari.");
    }
    const canvas = document.createElement("canvas");
    canvas.width = 720; canvas.height = 1280;
    const ctx = canvas.getContext("2d");
    const canvasStream = canvas.captureStream(24);
    const video = document.createElement("video");
    video.preload = "auto";
    video.playsInline = true;
    video.muted = false;
    video.volume = 1;
    let audioContext = null, audioStream = null;
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) {
        audioContext = new AudioCtx();
        const source = audioContext.createMediaElementSource(video);
        const gain = audioContext.createGain();
        const destination = audioContext.createMediaStreamDestination();
        gain.gain.value = 0.88;
        source.connect(gain);
        gain.connect(destination);
        audioStream = destination.stream;
        await audioContext.resume();
      }
    } catch (_) { audioStream = null; }
    const tracks = [...canvasStream.getVideoTracks(), ...(audioStream ? audioStream.getAudioTracks() : [])];
    const stream = new MediaStream(tracks);
    const mime = ["video/mp4;codecs=avc1.42E01E,mp4a.40.2", "video/mp4", "video/webm;codecs=vp9,opus", "video/webm"].find(type => MediaRecorder.isTypeSupported(type));
    if (!mime) throw new Error("L'enregistrement MP4 local n'est pas pris en charge par ce navigateur.");
    const recorder = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 5000000, audioBitsPerSecond: 128000 });
    const chunks = [];
    recorder.ondataavailable = event => { if (event.data && event.data.size) chunks.push(event.data); };
    const stopped = new Promise((resolve, reject) => {
      recorder.onstop = resolve;
      recorder.onerror = () => reject(new Error("Erreur pendant l'export vidéo local."));
    });
    recorder.start();
    try {
      for (let i = 0; i < shots.length; i++) {
        const shot = shots[i];
        setProgress(43 + (i / shots.length) * 54, "Assemblage du Reel · plan " + (i + 1) + "/" + shots.length);
        await readyVideo(video, shot.clip.url);
        await seek(video, shot.start);
        await video.play();
        const end = shot.start + shot.length;
        await new Promise((resolve, reject) => {
          let last = performance.now();
          let timedOut = false;
          const deadline = setTimeout(() => { timedOut = true; video.pause(); reject(new Error("Le rendu a été interrompu par Safari. Essaie un lot plus petit.")); }, (shot.length + 12) * 1000);
          const frame = () => {
            if (timedOut) return;
            drawCover(ctx, video, canvas.width, canvas.height);
            const elapsed = video.currentTime - shot.start;
            if (video.ended || video.currentTime >= end || elapsed >= shot.length) {
              clearTimeout(deadline);
              video.pause();
              resolve();
              return;
            }
            last = performance.now();
            requestAnimationFrame(frame);
          };
          requestAnimationFrame(frame);
        });
      }
      await wait(250);
      recorder.stop();
      await stopped;
    } catch (error) {
      if (recorder.state !== "inactive") recorder.stop();
      try { await stopped; } catch (_) {}
      throw error;
    } finally {
      video.pause();
      video.removeAttribute("src");
      video.load();
      stream.getTracks().forEach(track => track.stop());
      if (audioContext) await audioContext.close().catch(() => {});
    }
    const blob = new Blob(chunks, { type: mime.split(";")[0] });
    if (!blob.size) throw new Error("Le fichier exporté est vide. Réessaie avec moins de vidéos.");
    return blob;
  }

  async function generate() {
    if (busy) return;
    const clips = Array.isArray(window.rafaClips) ? window.rafaClips : [];
    if (!clips.length) { panel.hidden = false; setProgress(0, "Ajoute d'abord tes vidéos."); return; }
    if (clips.length > 100) { panel.hidden = false; setProgress(0, "Pour préserver la mémoire de l'iPhone, importe au maximum 100 vidéos par montage."); return; }
    busy = true; button.disabled = true; panel.hidden = false; download.hidden = true; preview.hidden = true;
    audit.textContent = ""; shotAudit.textContent = "";
    if (outputUrl) URL.revokeObjectURL(outputUrl);
    outputBlob = null; outputUrl = null;
    try {
      setProgress(1, "Préparation de l'analyse locale sur ton iPhone…");
      const candidates = await analyseClips(clips);
      const shots = chooseShots(candidates, clips);
      if (shots.length < 5) throw new Error("Pas assez de passages exploitables. Ajoute des vidéos plus longues ou mieux éclairées.");
      const total = shots.reduce((sum, shot) => sum + shot.length, 0);
      shotAudit.textContent = "Plans retenus : " + shots.map((shot, i) => (i + 1) + ". " + shot.clip.file.name + " · " + shot.start.toFixed(1) + "–" + (shot.start + shot.length).toFixed(1) + " s · score image " + Math.round(shot.score * 100) + "/100").join("  /  ");
      audit.textContent = clips.length === 1
        ? "Chronologie interne respectée · passages sélectionnés dans l'enregistrement."
        : "Ordre approximatif selon les dates de fichiers disponibles · vérifie la progression jour/soir, car Safari ne donne pas toujours la date réelle de tournage.";
      setProgress(42, "Analyse terminée · " + shots.length + " passages sélectionnés · " + Math.round(total) + " secondes.");
      outputBlob = await renderShots(shots);
      outputUrl = URL.createObjectURL(outputBlob);
      preview.src = outputUrl;
      preview.hidden = false;
      download.hidden = false;
      setProgress(100, "Aperçu prêt · regarde ton Reel avant de le télécharger.");
    } catch (error) {
      setProgress(0, "Le montage n'a pas abouti : " + (error && error.message ? error.message : "erreur inconnue"));
    } finally {
      busy = false;
      button.disabled = false;
    }
  }

  function downloadFinal() {
    if (!outputBlob || !outputUrl) return;
    const ext = outputBlob.type.includes("mp4") ? "mp4" : "webm";
    const anchor = document.createElement("a");
    anchor.href = outputUrl;
    anchor.download = "Rafa-Pizza-Reel." + ext;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setProgress(100, "Export lancé. Sur iPhone, ouvre le partage ou Fichiers si Safari te le propose.");
    download.disabled = true;
    setTimeout(() => {
      const clips = Array.isArray(window.rafaClips) ? window.rafaClips : [];
      clips.forEach(clip => URL.revokeObjectURL(clip.url));
      window.rafaClips = [];
      window.dispatchEvent(new Event("rafa-export-complete"));
      download.disabled = false;
    }, 30000);
  }

  button.addEventListener("click", generate);
  download.addEventListener("click", downloadFinal);
  button.disabled = false;
  panel.hidden = false;
  setProgress(0, "Moteur local prêt · tes vidéos restent sur cet iPhone.");
})();