# Rafa Studio — render service

This service is the first real server-side editing engine. It accepts resumable 8 MB chunks, inspects source footage with FFprobe/OpenCV, ranks candidate moments using visual quality signals, applies a conservative chronology order, renders a vertical H.264 MP4 with FFmpeg, serves a preview, and purges the temporary project after MP4 delivery or TTL expiry.

## Deploy

1. In Render, choose **New → Blueprint** and connect this repository.
2. Render reads the root `render.yaml` and creates `rafa-studio-api`. During setup, provide a private `RAFA_ACCESS_PASSWORD`; Render generates `RAFA_SESSION_SECRET` automatically. The web app asks for this password and receives a 12-hour signed session. Do not publish the password or put it in `config.js`.
3. After deployment, the API base URL is normally `https://rafa-studio-api.onrender.com`.
4. Set that URL as `window.RAFA_API_BASE` in the front-end `config.js` file and redeploy GitHub Pages.

The service needs a paid CPU instance for dependable video processing. Its working directory is temporary; do not attach a persistent disk. The app deletes project sources and intermediate files after successful MP4 delivery and expires abandoned projects after six hours.

## API

- `GET /health`
- `POST /api/auth/login` — exchange the private studio password for a short-lived session token
- `POST /api/projects` — create a project
- `PUT /api/projects/{id}/files/{f0000}/chunks/{index}` — upload an 8 MB chunk as multipart field `file`
- `POST /api/projects/{id}/complete` — join chunks and queue the edit
- `GET /api/projects/{id}` — job status and editorial audit
- `GET /api/projects/{id}/preview` — playable MP4 preview
- `GET /api/projects/{id}/download` — final MP4 transfer\n- `POST /api/projects/{id}/ack-download` — confirm complete transfer and delete all source/intermediate files
- `DELETE /api/projects/{id}` — cancel and delete a project

The upload and render endpoints require the short-lived `X-Rafa-Token` session. Configure `RAFA_ACCESS_PASSWORD` and `RAFA_SESSION_SECRET` on the backend; the frontend stores only the expiring session token in tab session storage. A separate `RAFA_API_TOKEN` can be used for private server-to-server access. Creation is also rate-limited by IP.

## Current editorial-engine scope

The engine samples frames and ranks them by sharpness, exposure, saturation and motion. When `OPENAI_API_KEY` is configured on the backend, it also sends only selected low-resolution JPEG still frames (never source video files) to the OpenAI Responses API for semantic labels such as dough, topping, guests, oven and finished pizza. Set the key in the Render service environment; it is optional, and the engine falls back to visual scoring if absent or unavailable. This external vision analysis can incur API charges. The model uses capture timestamps when trustworthy, otherwise a low-confidence brightness estimate to reduce obvious night-to-day reversals. This is an initial shot-understanding layer, not yet a full cinematic director: event clustering, action-phase timecodes, audio understanding and an editorial narrative planner remain to be built.

The chronology audit is returned with the job so the UI can disclose uncertainty. Do not present brightness-derived order as verified real-world time. Vision input handling follows the official [OpenAI image and vision guide](https://developers.openai.com/api/docs/guides/images-vision?api-mode=responses); image inputs are supported in the Responses API. The backend does not submit the raw video file to that API.
