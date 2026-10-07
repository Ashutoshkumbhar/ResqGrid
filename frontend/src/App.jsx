import React, { useState, useEffect, useRef, useCallback } from 'react';
import Navbar from './components/Navbar';
import SimulatorToolbar from './components/SimulatorToolbar';
import DashboardPage from './pages/DashboardPage';
import DisasterMapPage from './pages/DisasterMapPage';
import IncidentsPage from './pages/IncidentsPage';
import GroundReportsPage from './pages/GroundReportsPage';
import ResourcesRoutesPage from './pages/ResourcesRoutesPage';
import ImpactPage from './pages/ImpactPage';
import EvaluationReplayPage from './pages/EvaluationReplayPage';
import { api } from './utils';

const LAST_STATE_KEY = 'resqgrid:last-known-state';
const REPORT_QUEUE_KEY = 'resqgrid:offline-report-queue';

function readStoredJson(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function toDataUrl(file) {
  return new Promise((resolve) => {
    if (!file || typeof file.arrayBuffer !== 'function') {
      resolve(null);
      return;
    }
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => resolve(null);
    reader.readAsDataURL(file);
  });
}

function dataUrlToBlob(dataUrl) {
  const [header, payload] = dataUrl.split(',');
  const mimeMatch = header.match(/data:(.*?);base64/);
  const mime = mimeMatch ? mimeMatch[1] : 'application/octet-stream';
  const binary = atob(payload);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return new Blob([bytes], { type: mime });
}

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [systemState, setSystemStateRaw] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [toast, setToast] = useState(null);
  const [busy, setBusy] = useState(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [demoNarrations, setDemoNarrations] = useState([]);
  const [darkMode, setDarkMode] = useState(() => {
    try {
      return window.localStorage.getItem('resqgrid-theme') === 'dark';
    } catch {
      return false;
    }
  });
  const [isOffline, setIsOffline] = useState(() => !navigator.onLine);
  const [syncingQueue, setSyncingQueue] = useState(false);
  const toastTimer = useRef(null);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', darkMode ? 'dark' : 'light');
    try {
      window.localStorage.setItem('resqgrid-theme', darkMode ? 'dark' : 'light');
    } catch {
      // Ignore storage quota errors.
    }
  }, [darkMode]);

  // Responses can arrive out of order (poll vs. action vs. WebSocket); never replace newer state with older
  const setSystemState = useCallback((next) => {
    setSystemStateRaw((prev) => {
      const resolved = (!prev || !next?.version || next.instanceId !== prev.instanceId || next.version >= prev.version ? next : prev);
      if (resolved) {
        try {
          window.localStorage.setItem(LAST_STATE_KEY, JSON.stringify(resolved));
        } catch {
          // Ignore storage quota errors.
        }
      }
      return resolved;
    });
  }, []);

  const showToast = useCallback((msg, kind = 'info') => {
    setToast({ msg, kind });
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), kind === 'error' ? 6000 : 4000);
  }, []);

  const pushDemoNarration = useCallback((narration) => {
    if (!narration) return;
    setDemoNarrations((prev) => [...prev.slice(-6), narration]);
  }, []);

  const queueOfflineReport = useCallback((entry) => {
    const queue = readStoredJson(REPORT_QUEUE_KEY, []);
    queue.push({ ...entry, createdAt: new Date().toISOString() });
    try {
      window.localStorage.setItem(REPORT_QUEUE_KEY, JSON.stringify(queue));
    } catch {
      showToast('Storage is full; queued report could not be saved offline.', 'error');
      return;
    }
    showToast('Offline — report saved and will sync when the connection returns.', 'info');
  }, [showToast]);

  const syncOfflineQueue = useCallback(async () => {
    if (!navigator.onLine) return;
    const currentQueue = readStoredJson(REPORT_QUEUE_KEY, []);
    if (!currentQueue.length) return;
    setSyncingQueue(true);
    const remaining = [];
    for (const item of currentQueue) {
      try {
        if (item.type === 'report') {
          await api('/api/reports', item.payload, 'POST');
        } else if (item.type === 'report-photo') {
          const formData = new FormData();
          formData.append('text', item.payload?.text || '');
          if (item.payload?.latitude !== undefined) formData.append('latitude', String(item.payload.latitude));
          if (item.payload?.longitude !== undefined) formData.append('longitude', String(item.payload.longitude));
          if (item.imageDataUrl) {
            const blob = dataUrlToBlob(item.imageDataUrl);
            formData.append('image', blob, item.fileName || 'queued-report.jpg');
          }
          await api('/api/reports/photo', formData, 'POST');
        }
      } catch {
        remaining.push(item);
      }
    }
    try {
      window.localStorage.setItem(REPORT_QUEUE_KEY, JSON.stringify(remaining));
    } catch {
      // Ignore storage errors.
    }
    setSyncingQueue(false);
    if (remaining.length < currentQueue.length) {
      showToast('Queued reports synced successfully.', 'success');
    }
  }, [showToast]);

  const fetchState = useCallback(async () => {
    try {
      const freshState = await api('/api/state');
      setSystemState(freshState);
      setLoadError(null);
    } catch (err) {
      const cached = readStoredJson(LAST_STATE_KEY, null);
      if (cached && !systemState) {
        setSystemState(cached);
      }
      setLoadError(err.message);
      showToast('Using the last known state while the backend is unavailable.', 'error');
    } finally {
      setLoading(false);
    }
  }, [setSystemState, showToast, systemState]);

  useEffect(() => {
    if (typeof navigator !== 'undefined') {
      const handleNetwork = () => {
        const connected = navigator.onLine;
        setIsOffline(!connected);
        if (connected) {
          showToast('Back online — syncing queued reports.', 'success');
          syncOfflineQueue();
        }
      };
      window.addEventListener('online', handleNetwork);
      window.addEventListener('offline', handleNetwork);
      return () => {
        window.removeEventListener('online', handleNetwork);
        window.removeEventListener('offline', handleNetwork);
      };
    }
    return undefined;
  }, [showToast, syncOfflineQueue]);

  useEffect(() => {
    fetchState();
    let ws = null;
    let reconnectTimeout = null;
    let closed = false;

    const connect = () => {
      let wsUrl = import.meta.env?.VITE_WS_URL;
      if (!wsUrl) {
        const apiBase = (import.meta.env?.VITE_API_URL || '').replace(/\/$/, '');
        const isLocalDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
        if (apiBase) {
          wsUrl = `${apiBase.replace(/^http:/, 'ws:').replace(/^https:/, 'wss:')}/ws/live`;
        } else if (isLocalDev && window.location.port !== '8000') {
          wsUrl = `ws://${window.location.hostname}:8000/ws/live`;
        } else {
          const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
          wsUrl = `${proto}//${window.location.host}/ws/live`;
        }
      }
      ws = new WebSocket(wsUrl);
      ws.onopen = () => setWsConnected(true);
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.data) setSystemState(msg.data);
          if (['DEMO_STARTED', 'DEMO_STEP', 'DEMO_STOPPED'].includes(msg.type)) {
            pushDemoNarration(msg.narration);
          }
        } catch (e) {
          console.error('[ResQGrid WS] parse error', e);
        }
      };
      ws.onclose = () => {
        setWsConnected(false);
        if (!closed) reconnectTimeout = setTimeout(connect, 3000);
      };
      ws.onerror = () => ws.close();
    };
    connect();

    // REST fallback in case the socket drops
    const interval = setInterval(fetchState, 15000);
    return () => {
      closed = true;
      clearInterval(interval);
      clearTimeout(reconnectTimeout);
      if (ws) ws.close();
    };
  }, [fetchState, setSystemState, pushDemoNarration]);

  // Every action: loading state, error toast, state refresh from the response
  const run = useCallback(async (key, path, body, successMsg) => {
    setBusy(key);
    try {
      const data = await api(path, body ?? {});
      const next = data?.updatedState || data?.state;
      if (next) setSystemState(next);
      if (data?.demo?.narration) pushDemoNarration(data.demo.narration);
      if (successMsg) showToast(typeof successMsg === 'function' ? successMsg(data) : successMsg);
      return data;
    } catch (err) {
      showToast(`⚠️ ${err.message}`, 'error');
      return null;
    } finally {
      setBusy(null);
    }
  }, [showToast, setSystemState, pushDemoNarration]);

  const actions = {
    step: (n) => run(`step-${n}`, `/api/simulate/step/${n}`, {}, (d) => d.title),
    rainfall: (incrementMm = 50) => run('rainfall', '/api/simulate/rainfall', { incrementMm }, `Added ${incrementMm} mm of rain — plan updated`),
    waterLevel: (incrementM = 0.5) => run('water', '/api/simulate/waterlevel', { incrementM }, `River level raised ${incrementM} m — plan updated`),
    setRoad: (roadId, status) => run(`road-${roadId}`, '/api/simulate/road-blockage', { roadId, status },
      (d) => `Road ${roadId} is now ${d.updatedState.roads.find((r) => r.id === roadId)?.status.replace('_', ' ').toLowerCase()} — routes rechecked`),
    report: async (payload) => {
      if (!navigator.onLine) {
        queueOfflineReport({ type: 'report', payload });
        return { queued: true };
      }
      return run('report', '/api/reports', payload,
        (d) => `Report ${d.report.id} read by AI (${Math.round((d.report.extractedInfo?.confidence || 0) * 100)}% confidence) — plan updated`);
    },
    reportPhoto: async (formData) => {
      if (!navigator.onLine) {
        const dataUrl = await toDataUrl(formData.get('image'));
        queueOfflineReport({
          type: 'report-photo',
          payload: {
            text: String(formData.get('text') || ''),
            latitude: formData.get('latitude') !== null ? Number(formData.get('latitude')) : undefined,
            longitude: formData.get('longitude') !== null ? Number(formData.get('longitude')) : undefined,
          },
          imageDataUrl: dataUrl,
          fileName: formData.get('image')?.name || 'offline-report.jpg',
        });
        return { queued: true };
      }
      return run('report-photo', '/api/reports/photo', formData,
        (d) => `Photo report uploaded — ${d.parsed?.manualReview ? 'manual review required' : 'AI parsed flood conditions'} — plan updated`);
    },
    scenario: (settlementId, scenario, apply) => run(`scenario-${scenario}`, '/api/routes/validate', { settlementId, scenario, apply },
      apply ? `Test ${scenario} applied to the live map` : null),
    resourceStatus: (id, status, assignment) => run(`res-${id}`, `/api/resources/${id}/status`, { status, assignment },
      `${id} is now ${status.toLowerCase()}`),
    explain: (settlementId) => run('explain', '/api/explain', { settlementId }),
    replay: () => run('replay', '/api/simulate/replay', {}, 'Replay started (not live data)'),
    stopReplay: () => run('replay-stop', '/api/simulate/replay/stop', {}, 'Replay paused'),
    reset: () => run('reset', '/api/simulate/reset', {}, 'Reset to a normal day'),
    live: () => run('live', '/api/simulate/real-world-live', {}, "Now using today's real rainfall"),
    demoStart: () => run('demo-start', '/api/demo/start', {}, (d) => d.demo?.narration || 'Demo story started'),
    demoStop: () => run('demo-stop', '/api/demo/stop', {}, 'Demo story stopped'),
  };

  if (!systemState) {
    return (
      <div style={{ minHeight: '100vh', background: '#090f1d', color: '#fff', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
        <div style={{ fontSize: 20, fontWeight: 800 }}>ResQGrid Decision Platform</div>
        <div style={{ fontSize: 13, color: loadError ? '#f87171' : '#94a3b8' }}>
          {loading ? 'Connecting to the ResQGrid backend…' : `Backend unreachable: ${loadError}. Start it with: cd backend_py && .venv\\Scripts\\python -m uvicorn main:app --port 8000`}
        </div>
        {!loading && <button className="btn btn-primary" onClick={() => { setLoading(true); fetchState(); }}>Retry</button>}
      </div>
    );
  }

  const pageProps = { systemState, actions, busy, demoNarrations };

  return (
    <div className="app-container">
      {isOffline && <div className="offline-banner">Offline mode — last known state is available and queued reports will sync automatically when connectivity returns.</div>}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        systemState={systemState}
        onReset={actions.reset}
        wsConnected={wsConnected}
        isOffline={isOffline}
        darkMode={darkMode}
        onToggleTheme={() => setDarkMode((prev) => !prev)}
        syncingQueue={syncingQueue}
      />
      <SimulatorToolbar {...pageProps} />

      <main style={{ flex: 1 }}>
        {activeTab === 'dashboard' && <DashboardPage {...pageProps} />}
        {activeTab === 'map' && <DisasterMapPage {...pageProps} />}
        {activeTab === 'incidents' && <IncidentsPage {...pageProps} />}
        {activeTab === 'reports' && <GroundReportsPage {...pageProps} />}
        {activeTab === 'routes' && <ResourcesRoutesPage {...pageProps} />}
        {activeTab === 'impact' && <ImpactPage />}
        {activeTab === 'accuracy' && <EvaluationReplayPage {...pageProps} mode="accuracy" />}
        {activeTab === 'replay' && <EvaluationReplayPage {...pageProps} mode="replay" />}
      </main>

      {toast && (
        <div style={{
          position: 'fixed', bottom: 24, right: 24, zIndex: 9999, maxWidth: 420,
          background: toast.kind === 'error' ? '#7f1d1d' : '#0f172a', color: '#fff',
          padding: '12px 18px', borderRadius: 8, fontSize: 13, fontWeight: 600,
          border: `1px solid ${toast.kind === 'error' ? '#ef4444' : '#334155'}`, boxShadow: '0 10px 25px rgba(0,0,0,0.4)',
        }}>
          {toast.msg}
        </div>
      )}
    </div>
  );
}
