import React, { useEffect, useState } from 'react';
import { History, Play, Square, RotateCcw, FileCheck, Info, Loader2 } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid, BarChart, Bar, Cell, ReferenceLine } from 'recharts';
import { api, shortName } from '../utils';

const LINE_COLORS = ['#dc2626', '#ea580c', '#2563eb', '#16a34a', '#7c3aed'];
const VERDICT = {
  CORRECT_ALERT: ['#dcfce7', '#166534', 'Correct alert'],
  CORRECT_NO_ALERT: ['#f1f5f9', '#334155', 'Correct — no alert'],
  FALSE_ALERT: ['#fee2e2', '#991b1b', 'False alert'],
  MISSED_EVENT: ['#fef3c7', '#92400e', 'Missed event'],
};

export default function EvaluationReplayPage({ systemState, actions, busy, mode = 'replay' }) {
  const [evalData, setEvalData] = useState(null);
  const [evalError, setEvalError] = useState(null);
  const replay = systemState.replay;
  const isReplay = systemState.mode === 'REPLAYED_DATA';
  const settlements = [...systemState.settlements].sort((a, b) => a.id.localeCompare(b.id));

  useEffect(() => {
    api('/api/accuracy').then(setEvalData).catch((e) => setEvalError(e.message));
  }, []);

  const summary = evalData ? [
    { name: 'Correct alerts', value: evalData.correctAlerts, color: '#16a34a' },
    { name: 'False alerts', value: evalData.falseAlerts, color: '#dc2626' },
    { name: 'Missed events', value: evalData.missedEvents, color: '#d97706' },
    { name: 'Correct no-alert', value: evalData.correctNoAlert, color: '#64748b' },
  ] : [];

  const confusionChart = evalData?.matrixChart || [];

  return (
    <div style={{ padding: 24, maxWidth: 1240, margin: '0 auto' }}>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 24, fontWeight: 800, margin: 0 }}>{mode === 'accuracy' ? 'Accuracy Dashboard' : 'Replay & False-Alert Evaluation'}</h1>
      </div>

      <div className="panel-card" style={{ border: isReplay ? '2px solid #dc2626' : '1px solid #cbd5e1' }}>
        <div className="panel-header" style={{ background: isReplay ? '#fef2f2' : '#fafafa' }}>
          <div className="panel-title" style={{ color: isReplay ? '#991b1b' : '#0f172a' }}><History size={18} /><span>Historical / replay mode</span></div>
          {isReplay
            ? <span style={{ fontSize: 13, background: '#dc2626', color: '#fff', fontWeight: 800, padding: '4px 12px', borderRadius: 4, letterSpacing: '0.5px' }}>REPLAYED / NOT LIVE</span>
            : <span style={{ fontSize: 11, color: '#64748b' }}>Current mode: {systemState.mode.replace('_', ' ')}</span>}
        </div>
        <div className="panel-body">
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 20, flexWrap: 'wrap', alignItems: 'center' }}>
            <div style={{ fontSize: 12, color: '#475569', lineHeight: 1.6 }}>
              <div><b>Event:</b> Heavy Rainfall Scenario — Mula-Pawana Basin</div>
              <div><b>Date:</b> 15 August 2026 · <b>Mode:</b> REPLAYED DATA (reconstructed scenario)</div>
              <div>Rainfall ↑ → Risk ↑ → Affected area ↑ → Priority → Road → Route → Resource — one frame every 4 s.</div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {replay?.running ? (
                <button className="btn btn-danger" onClick={actions.stopReplay}><Square size={13} /> Pause</button>
              ) : (
                <button className="btn btn-danger" onClick={actions.replay} disabled={!!busy}>{busy === 'replay' ? <Loader2 size={13} className="spin" /> : <Play size={13} />} {replay ? 'Restart replay' : 'Start replay'}</button>
              )}
              <button className="btn btn-secondary" onClick={actions.reset} disabled={!!busy}><RotateCcw size={13} /> Exit to baseline</button>
            </div>
          </div>

          {replay && (
            <>
              <div style={{ display: 'flex', gap: 4, margin: '14px 0 6px' }}>
                {Array.from({ length: replay.totalFrames }).map((_, i) => (
                  <div key={i} style={{ flex: 1, height: 6, borderRadius: 3, background: i < replay.frame ? '#dc2626' : '#e2e8f0' }} />
                ))}
              </div>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#991b1b' }}>
                {replay.date} {replay.frameTime} — frame {replay.frame}/{replay.totalFrames}: {replay.label}
              </div>
              <div style={{ height: 240, marginTop: 10 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={replay.history} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="time" tick={{ fontSize: 11 }} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <ReferenceLine y={81} stroke="#dc2626" strokeDasharray="4 4" label={{ value: 'CRITICAL', fontSize: 10, fill: '#dc2626' }} />
                    <ReferenceLine y={61} stroke="#ea580c" strokeDasharray="4 4" label={{ value: 'HIGH', fontSize: 10, fill: '#ea580c' }} />
                    {settlements.map((s, i) => (
                      <Line key={s.id} type="monotone" dataKey={s.id} name={`${shortName(s.name)} risk`} stroke={LINE_COLORS[i % LINE_COLORS.length]} strokeWidth={2} dot isAnimationActive={false} />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </>
          )}
        </div>
      </div>

      <div className="panel-card">
        <div className="panel-header">
          <div className="panel-title"><FileCheck size={18} color="#16a34a" /><span>False-alert evaluation</span></div>
          <span style={{ fontSize: 10, background: '#fef3c7', color: '#92400e', fontWeight: 700, padding: '2px 8px', borderRadius: 4 }}>SCENARIO-BASED</span>
        </div>
        <div className="panel-body">
          <div style={{ background: '#fffbeb', border: '1px solid #fde68a', padding: '10px 14px', borderRadius: 6, fontSize: 12, color: '#92400e', display: 'flex', gap: 8, marginBottom: 16 }}>
            <Info size={16} style={{ flexShrink: 0 }} />
            <span><b>Evaluation uses simulated and replayed scenarios</b>, not real-world outcomes. Each scenario is run through the same risk engine used live; an alert = HIGH or CRITICAL.</span>
          </div>
          {evalError && <div style={{ color: '#dc2626', fontSize: 12 }}>Could not load evaluation: {evalError}</div>}
          {evalData && (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12, marginBottom: 16 }}>
                {[
                  ['Total alerts', evalData.totalAlerts, '#0f172a'],
                  ['Correct alerts', evalData.correctAlerts, '#16a34a'],
                  ['False alerts', evalData.falseAlerts, '#dc2626'],
                  ['False alert rate', `${evalData.falseAlertRatePercent}%`, '#2563eb'],
                  ['Missed events', evalData.missedEvents, '#d97706'],
                  ['Precision', `${evalData.precisionPercent}%`, '#7c3aed'],
                  ['Recall', `${evalData.recallPercent}%`, '#6d28d9'],
                  ['Avg lead time', `${evalData.averageLeadTimeMinutes} min`, '#0f766e'],
                ].map(([k, v, c]) => (
                  <div key={k} style={{ background: '#f8fafc', padding: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}>
                    <div style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>{k}</div>
                    <div style={{ fontSize: 24, fontWeight: 800, color: c, fontFamily: 'monospace' }}>{v}</div>
                  </div>
                ))}
              </div>
              <div style={{ height: 180, marginBottom: 16 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={summary} layout="vertical" margin={{ left: 40 }}>
                    <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                    <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={110} />
                    <Tooltip />
                    <Bar dataKey="value" radius={[0, 4, 4, 0]}>{summary.map((d) => <Cell key={d.name} fill={d.color} />)}</Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              {confusionChart.length > 0 && (
                <div style={{ height: 180, marginBottom: 16 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={confusionChart} margin={{ top: 10, right: 10, left: -20, bottom: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                      <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
                      <Tooltip />
                      <Bar dataKey="value" fill="#2563eb" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
              <div style={{ fontSize: 11, color: '#64748b', marginBottom: 8 }}>{evalData.totalScenarios} scenarios · {evalData.evaluationDataset} · threshold: {evalData.alertThreshold}</div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: '#f1f5f9', textAlign: 'left' }}>
                      {['Case', 'Location', 'Scenario', 'Signals', 'Risk', 'Engine output', 'Outcome', 'Verdict'].map((h) => <th key={h} style={{ padding: '7px 8px' }}>{h}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {evalData.cases.map((c) => {
                      const [bg, fg, label] = VERDICT[c.verdict];
                      return (
                        <tr key={c.caseId} style={{ borderBottom: '1px solid #e2e8f0' }}>
                          <td style={{ padding: '6px 8px', fontFamily: 'monospace' }}>{c.caseId}</td>
                          <td style={{ padding: '6px 8px' }}>{c.location}</td>
                          <td style={{ padding: '6px 8px', color: '#475569' }}>{c.scenario}</td>
                          <td style={{ padding: '6px 8px', color: '#475569' }}>{c.signal}</td>
                          <td style={{ padding: '6px 8px', fontFamily: 'monospace' }}>{c.riskScore}</td>
                          <td style={{ padding: '6px 8px', fontWeight: 700 }}>{c.alertDecision}</td>
                          <td style={{ padding: '6px 8px' }}>{c.observed.replace('_', ' ')}</td>
                          <td style={{ padding: '6px 8px' }}><span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 700, background: bg, color: fg }}>{label}</span></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
