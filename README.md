# Rafa Studio

Rafa Studio is a mobile-first, browser-local video editing prototype for Rafa Pizza.

## Current front-end workflow

- Hosted as a static GitHub Pages site.
- Select local video files on iPhone Safari; source clips are not uploaded to a remote processing server.
- The browser samples frames and ranks candidate moments using visual quality signals (exposure, contrast, edge detail, color and approximate motion).
- It selects distinct moments and assembles a vertical 720 × 1280 Reel using the browser canvas and MediaRecorder APIs.
- A preview is shown before the user triggers the MP4/WebM export.
- The app does not retain a permanent media library. Source object URLs are released after the export is triggered or the page is closed.

## Important limitations

This is an experimental local editing engine, not yet a professional AI editor. It does not currently understand food-specific semantic roles (dough, topping, oven, guests), detect action boundaries reliably, understand music/audio rhythm, or infer the true capture date from every iPhone file. Multi-file ordering uses the file modification dates available to the browser and must be checked by the user.

Safari/iOS support for canvas capture, MediaRecorder containers/codecs, audio routing, and large video decoding varies by device and file format. Long 4K recordings or very large batches may exceed available memory or take too long. The first real validation must be performed on the target iPhone with representative clips.

## Experimental server engine

The `backend/` directory and `render.yaml` preserve the earlier optional FFmpeg server prototype. They are not required by the current GitHub Pages local workflow. The Render service configuration uses a paid Starter instance for dependable video processing; do not deploy it if the goal is a zero-cost setup.

## Development

The local front-end engine is in `engine-client.js`; the UI and file selection are in `index.html`. GitHub Pages deploys on pushes to `main`.
