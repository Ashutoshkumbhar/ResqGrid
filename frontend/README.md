# ResQGrid Frontend

This frontend provides the control-room dashboard for flood monitoring, emergency planning, and live operations.

## Local setup

```bash
cd frontend
npm install
npm run dev
```

The app runs on http://localhost:5173 by default and connects to the Python API on http://localhost:8000 unless `VITE_API_URL` or `VITE_WS_URL` is set.

## PWA and offline support

- The app registers a service worker for offline startup and cached assets.
- The last known backend state is kept in local storage and restored when the server is unavailable.
- Reports created offline are queued locally and replayed automatically once connectivity returns.
- OSM map tiles are cached in the browser after first successful load.

## Screenshots placeholders

- Dashboard overview: ![Dashboard placeholder](https://placehold.co/1200x700/0f172a/93c5fd?text=Dashboard+Overview)
- Flood map: ![Map placeholder](https://placehold.co/1200x700/111827/fbbf24?text=Disaster+Map)
- Operations timeline: ![Timeline placeholder](https://placehold.co/1200x700/0b1120/38bdf8?text=Operations+Timeline)
