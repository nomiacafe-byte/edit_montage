# Rafa Studio — render service

This service is the first real server-side editing engine. It accepts resumable 8 MB chunks, inspects source footage with FFprobe/OpenCV, ranks candidate moments using visual quality signals, applies a conservative chronology order, renders a vertical H.264 MP4 with FFmpeg, serves a preview, and purges the temporary project after MP4 delivery or TTL expiry.

## Deploy

1. In Render, choose **New → Blueprint** and connect this repository.
2. Render reads the root `render.yaml` and creates `rafa-studio-api`.
3. After deployment, the API base URL is normally `https://rafa-studio-api.onrender.com`.
4. Set that URL as `window.RAFA_API_BASE` in the front-end `config.js` file and redeploy GitHub Pages.

The service needs a paid CPU instance for dependable video processing. Its working directory is temporary; do not attach a persistent disk. The app deletes project sources and intermediate files after successful MP4 delivery and expires abandoned projects after six hours.

## API

- `GET /health`
- `POST /api/projects` — create a project
- `PUT /api/projects/{id}/files/{f0000}/chunks/{index}` — upload an 8 MB chunk as multipart field `file`
- `POST /api/projects/{id}/complete` — join chunks and queue the edit
- `GET /api/projects/{id}` — job status and editorial audit
- `GET /api/projects/{id}/preview` — playable MP4 preview
- `GET /api/projects/{id}/download` — final MP4 transfer\n- `POST /api/projects/{id}/ack-download` — confirm complete transfer and delete all source/intermediate files
- `DELETE /api/projects/{id}` — cancel and delete a project

Optional `X-Rafa-Token` authentication is supported through `RAFA_API_TOKEN`. Do not place a long-lived secret in a public static front end. Before public launch, put the API behind an authenticated upload gateway/rate limiter and add durable job storage/queueing.

## Current editorial-engine scope

This is a real deterministic first render engine, not semantic AI. It samples frames and ranks them by sharpness, exposure, saturation and motion; it uses reliable capture timestamps when available, otherwise a low-confidence brightness estimate to reduce obvious night-to-day reversals. It cannot yet reliably recognize dough stretching, toppings, guests, oven moments, event boundaries, or understand story semantics. Those require a vision model and event-aware editorial planner, which are the next engine milestone.

The chronology audit is returned with the job so the UI can disclose uncertainty. Do not present brightness-derived order as verified real-world time.
