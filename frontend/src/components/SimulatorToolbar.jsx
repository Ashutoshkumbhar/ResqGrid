import React, { useState } from 'react';
import { Loader2 } from 'lucide-react';

const STEPS = [
  { num: 1, label: 'Normal day' },
  { num: 2, label: 'Heavy rain' },
  { num: 3, label: 'Field report' },
  { num: 4, label: 'Road closed' },
  { num: 5, label: 'Re-route' },
  { num: 6, label: 'Final plan' },
];

const btn = {
  fontSize: 12, padding: '6px 12px', borderRadius: 6, border: '1px solid #334155',
  background: '#1e293b', color: '#e2e8f0', cursor: 'pointer', fontWeight: 600, whiteSpace: 'nowrap',
  display: 'inline-flex', alignItems: 'center', gap: 6,
};

export default function SimulatorToolbar({ systemState, actions, busy }) {
  const roads = systemState?.roads || [];
  const [roadId, setRoadId] = useState('R12');
  const [open, setOpen] = useState(false);
  const road = roads.find((r) => r.id === roadId);
  const isBlocked = road?.status === 'BLOCKED';
  const sim = systemState?.simulation || {};
  const replay = systemState?.replay;
  const isReplay = systemState?.mode === 'REPLAYED_DATA';
  const isLive = systemState?.mode === 'LIVE';
  const currentStep = isReplay || isLive ? 0 : sim.step;
  const spin = (key) => busy === key && <Loader2 size={12} className="spin" />;

  return (
    <div style={{ background: '#0b1329', borderBottom: '1px solid #1e293b', padding: '10px 24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
        {/* Guided walkthrough */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 12, color: '#94a3b8', fontWeight: 600 }}>Walkthrough</span>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            {STEPS.map((st, i) => {
              const done = currentStep > st.num;
              const active = currentStep === st.num;
              return (
                <React.Fragment key={st.num}>
                  {i > 0 && <div style={{ width: 14, height: 2, background: done || active ? '#3b82f6' : '#334155' }} />}
                  <button
                    onClick={() => actions.step(st.num)}
                    disabled={!!busy}
                    title={`Step ${st.num}: ${st.label}`}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 6, padding: '4px 10px 4px 4px', borderRadius: 20, cursor: 'pointer',
                      border: `1px solid ${active ? '#3b82f6' : '#334155'}`, background: active ? '#1d4ed8' : 'transparent',
                      color: active ? '#fff' : done ? '#bfdbfe' : '#94a3b8', fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap',
                    }}
                  >
                    <span style={{
                      width: 20, height: 20, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11,
                      background: active ? '#fff' : done ? '#3b82f6' : '#1e293b', color: active ? '#1d4ed8' : '#fff',
                    }}>
                      {busy === `step-${st.num}` ? <Loader2 size={11} className="spin" /> : st.num}
                    </span>
                    {st.label}
                  </button>
                </React.Fragment>
              );
            })}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <button style={{ ...btn, background: '#2563eb', borderColor: '#60a5fa', color: '#eff6ff' }} onClick={actions.demoStart} disabled={!!busy}>{spin('demo-start')}Run Demo</button>
          <button style={{ ...btn, background: open ? '#334155' : '#1e293b' }} onClick={() => setOpen(!open)}>
            {open ? 'Hide controls' : 'Change conditions'}
          </button>
          <button style={btn} onClick={actions.reset} disabled={!!busy}>{spin('reset')}Reset</button>
        </div>
      </div>

      {open && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginTop: 10 }}>
          <button style={btn} onClick={() => actions.rainfall(50)} disabled={!!busy} title="Add 50 mm of rain in every village">{spin('rainfall')}Add rain (+50 mm)</button>
          <button style={btn} onClick={() => actions.waterLevel(0.5)} disabled={!!busy} title="Raise river levels by 0.5 m">{spin('water')}Raise river (+0.5 m)</button>
          <span style={{ display: 'inline-flex', border: `1px solid ${isBlocked ? '#ef4444' : '#334155'}`, borderRadius: 6, overflow: 'hidden' }}>
            <select value={roadId} onChange={(e) => setRoadId(e.target.value)} style={{ background: '#0f172a', color: '#e2e8f0', border: 'none', fontSize: 12, padding: '0 8px' }}>
              {roads.map((r) => <option key={r.id} value={r.id}>{r.id} — {r.name} ({r.status.replace('_', ' ').toLowerCase()})</option>)}
            </select>
            <button style={{ ...btn, border: 'none', borderRadius: 0, background: isBlocked ? '#dc2626' : '#1e293b' }}
              onClick={() => actions.setRoad(roadId, isBlocked ? 'OPEN' : 'BLOCKED')} disabled={!!busy}>
              {spin(`road-${roadId}`)}{isBlocked ? 'Re-open road' : 'Close road'}
            </button>
          </span>
          <button style={{ ...btn, borderColor: '#059669', color: '#a7f3d0' }} onClick={actions.live} disabled={!!busy} title="Use today's real rainfall from Open-Meteo">
            {spin('live')}Use today's real weather
          </button>
        </div>
      )}

      <div style={{
        marginTop: 10, fontSize: 13, color: '#e2e8f0', background: isReplay ? 'rgba(127,29,29,0.5)' : 'rgba(30,41,59,0.7)',
        padding: '6px 12px', borderRadius: 6, borderLeft: `3px solid ${isReplay ? '#ef4444' : '#38bdf8'}`,
      }}>
        {isReplay && replay ? (
          <><b style={{ color: '#fecaca' }}>Replay (not live) — {replay.date} {replay.frameTime}:</b> {replay.label}</>
        ) : (
          <><b style={{ color: '#7dd3fc' }}>What's happening:</b> {sim.description}</>
        )}
      </div>
    </div>
  );
}
