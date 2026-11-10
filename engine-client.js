(() => {
  const apiBase = String(window.RAFA_API_BASE || "").replace(/\/$/, "");
  const token = window.RAFA_API_TOKEN || "";
  const $ = (id) => document.getElementById(id);
  const button = $("generate");
  const panel = $("renderPanel");
  const progress = $("renderProgress");
  const message = $("renderMessage");
  const preview = $("renderPreview");
  const download = $("downloadFinal");
  const audit = $("chronologyAudit");
  let activeProject = null;
  let previewUrl = null;
  let busy = false;

  const headers = (extra = {}) => token ? { ...extra, "X-Rafa-Token": token } : extra;
  const setProgress = (value, label) => {
    progress.value = Math.max(0, Math.min(100, value));
    message.textContent = label;
  };
  const request = async (url, options = {}) => {
    const response = await fetch(apiBase + url, { ...options, headers: headers(options.headers || {}) });
    if (!response.ok) {
      let detail = response.status + " " + response.statusText;
      try { const body = await response.json(); detail = body.detail || body.error || detail; } catch (_) {}
      throw new Error(detail);
    }
    return response;
  };
  const pause = (ms) => new Promise(resolve => setTimeout(resolve, ms));

  async function uploadWithRetry(projectId, file, fileIndex, totalBytes, uploadedBefore) {
    const chunkSize = 8 * 1024 * 1024;
    const chunks = Math.ceil(file.size / chunkSize);
    const fileId = "f" + String(fileIndex).padStart(4, "0");
    let uploaded = 0;
    for (let index = 0; index < chunks; index++) {
      const part = file.slice(index * chunkSize, Math.min(file.size, (index + 1) * chunkSize));
      let success = false;
      let lastError;
      for (let attempt = 0; attempt < 4 && !success; attempt++) {
        try {
          const form = new FormData();
          form.append("file", part, file.name + ".part");
          await request("/api/projects/" + projectId + "/files/" + fileId + "/chunks/" + index, {
            method: "PUT", body: form
          });
          success = true;
        } catch (error) {
          lastError = error;
          if (attempt < 3) await pause(700 * (attempt + 1));
        }
      }
      if (!success) throw new Error("Échec du téléversement de " + file.name + " : " + (lastError?.message || "réseau indisponible"));
      uploaded += part.size;
      const percent = 5 + ((uploadedBefore + uploaded) / totalBytes) * 50;
      setProgress(percent, "Téléversement · " + file.name + " · " + Math.round(percent - 5) + "%");
    }
    return { filename: file.name, size: file.size, chunks };
  }

  async function pollJob(projectId) {
    for (;;) {
      const response = await request("/api/projects/" + projectId);
      const job = await response.json();
      const phaseProgress = Math.max(55, Math.min(95, Number(job.progress || 55)));
      setProgress(phaseProgress, job.message || "Montage en cours…");
      if (job.audit) {
        const mode = job.audit.mode === "capture-timestamps" ? "Horodatages des fichiers" : "Estimation visuelle de la lumière";
        audit.textContent = "Chronologie : " + mode + " · confiance " + job.audit.chronology_confidence + ". " + job.audit.note;
      }
      if (job.status === "preview_ready") return job;
      if (job.status === "error") throw new Error(job.error || job.message || "Le rendu a échoué.");
      await pause(2200);
    }
  }

  async function generate() {
    if (busy) return;
    if (!apiBase) {
      message.textContent = "Le moteur serveur n'est pas configuré. Déploie le service backend, puis renseigne config.js.";
      panel.hidden = false;
      return;
    }
    const clips = Array.isArray(window.rafaClips) ? window.rafaClips : [];
    if (!clips.length) {
      message.textContent = "Ajoute d'abord tes vidéos dans la bibliothèque.";
      panel.hidden = false;
      return;
    }
    if (clips.length > 1000) {
      message.textContent = "Limite actuelle : 1 000 fichiers par projet.";
      panel.hidden = false;
      return;
    }
    busy = true;
    button.disabled = true;
    panel.hidden = false;
    download.hidden = true;
    preview.hidden = true;
    audit.textContent = "";
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    try {
      const totalBytes = clips.reduce((sum, clip) => sum + clip.file.size, 0);
      setProgress(1, "Préparation du projet privé…");
      const create = await request("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filenames: clips.map(c => c.file.name) })
      });
      const created = await create.json();
      activeProject = created.project_id;
      const completedFiles = [];
      let uploadedBefore = 0;
      for (let i = 0; i < clips.length; i++) {
        const result = await uploadWithRetry(activeProject, clips[i].file, i, totalBytes, uploadedBefore);
        completedFiles.push(result);
        uploadedBefore += clips[i].file.size;
      }
      setProgress(56, "Téléversement terminé · préparation de l'analyse…");
      await request("/api/projects/" + activeProject + "/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ files: completedFiles })
      });
      const job = await pollJob(activeProject);
      setProgress(100, "Aperçu prêt · regarde le montage avant de télécharger.");
      const previewResponse = await request("/api/projects/" + activeProject + "/preview");
      const blob = await previewResponse.blob();
      previewUrl = URL.createObjectURL(blob);
      preview.src = previewUrl;
      preview.hidden = false;
      download.hidden = false;
      message.textContent = "Ton Reel est prêt à être visionné. Le projet source reste temporaire jusqu'au téléchargement.";
      if (job.audit?.mode === "visual-light-estimate") {
        audit.textContent += " Vérifie particulièrement l'ordre jour/soir/nuit : l'estimation par luminosité peut se tromper entre événements différents.";
      }
    } catch (error) {
      message.textContent = "Le montage a été interrompu : " + error.message;
      if (activeProject) {
        try { await request("/api/projects/" + activeProject, { method: "DELETE" }); } catch (_) {}
      }
      activeProject = null;
    } finally {
      busy = false;
      button.disabled = false;
    }
  }

  async function downloadFinal() {
    if (!activeProject) return;
    download.disabled = true;
    message.textContent = "Préparation du téléchargement MP4…";
    try {
      const response = await request("/api/projects/" + activeProject + "/download");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "Rafa-Pizza-Reel.mp4";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
      message.textContent = "Téléchargement lancé. Le serveur supprime le projet et les rushes après livraison.";
      activeProject = null;
      download.hidden = true;
    } catch (error) {
      message.textContent = "Téléchargement non terminé : " + error.message + ". Le projet reste disponible pour réessayer.";
    } finally {
      download.disabled = false;
    }
  }

  button.addEventListener("click", generate);
  download.addEventListener("click", downloadFinal);
  if (!apiBase) {
    button.title = "Le moteur serveur doit être déployé avant la génération.";
  }
  window.addEventListener("beforeunload", () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  });
})();
