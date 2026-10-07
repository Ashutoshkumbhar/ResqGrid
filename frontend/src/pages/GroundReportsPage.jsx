import React, { useState, useEffect } from 'react';
import { FileText, Send, Sparkles, CheckCircle, Loader2, Mic, MapPin, Camera, LocateFixed } from 'lucide-react';
import { STAGE_COLORS, fmtAgo, pct } from '../utils';

const PRESETS = [
  { text: 'Bridge near Village A is blocked and water has entered nearby houses.', loc: 'S1', sev: 'HIGH', rep: 'CITIZEN' },
  { text: 'Wakad bridge confirmed submerged by our team, vehicles cannot cross.', loc: 'S1', sev: 'HIGH', rep: 'FIRST_RESPONDER' },
  { text: 'Sangvi river embankment overflowing, riverside link road impassable.', loc: 'S2', sev: 'CRITICAL', rep: 'WARD_OFFICER' },
  { text: 'Water rising near Dapodi confluence market, road waterlogged.', loc: 'S5', sev: 'MODERATE', rep: 'CITIZEN' },
];

const field = { width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #cbd5e1', fontSize: 13, background: '#fff' };
const label = { display: 'block', fontSize: 12, fontWeight: 700, color: '#334155', marginBottom: 4 };

function localNow() {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

export default function GroundReportsPage({ systemState, actions, busy }) {
  const settlements = [...systemState.settlements].sort((a, b) => a.id.localeCompare(b.id));
  const [description, setDescription] = useState(PRESETS[0].text);
  const [locationId, setLocationId] = useState('S1');
  const [severity, setSeverity] = useState('HIGH');
  const [reporterType, setReporterType] = useState('CITIZEN');
  const [timestamp, setTimestamp] = useState(localNow());
  const [last, setLast] = useState(null);
  const submitting = busy === 'report';

  const onSubmit = async (e) => {
    e.preventDefault();
    if (description.trim().length < 5) return;
    const loc = settlements.find((s) => s.id === locationId);
    const data = await actions.report({
      description: description.trim(), location: loc?.name || locationId, severity, reporterType,
      timestamp: timestamp ? new Date(timestamp).toISOString() : undefined,
    });
    if (data?.report) setLast(data.report);
  };

  return (
    <div style={{ padding: 24, maxWidth: 1240, margin: '0 auto' }}>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 24, fontWeight: 800, margin: 0 }}>Ground Reports</h1>
        <p style={{ fontSize: 13, color: '#64748b', marginTop: 4 }}>
          LLM extracts structured fields → system logic updates roads, risk, priority, routes and resources.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(340px, 460px) 1fr', gap: 24, alignItems: 'start' }}>
        <div className="panel-card">
          <div className="panel-header">
            <div className="panel-title"><FileText size={16} color="#2563eb" /><span>+ Submit Ground Report</span></div>
          </div>
          <div className="panel-body">
            <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, marginBottom: 6 }}>Example reports:</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 14 }}>
              {PRESETS.map((p, i) => (
                <button key={i} type="button" className="btn btn-secondary" style={{ fontSize: 11, textAlign: 'left', padding: '6px 8px', justifyContent: 'flex-start' }}
                  onClick={() => { setDescription(p.text); setLocationId(p.loc); setSeverity(p.sev); setReporterType(p.rep); setTimestamp(localNow()); }}>
                  {p.rep === 'CITIZEN' ? '👤' : '🛡️'} "{p.text}"
                </button>
              ))}
            </div>

            <form onSubmit={onSubmit}>
              <div style={{ marginBottom: 12 }}>
                <label style={label}>Location</label>
                <select value={locationId} onChange={(e) => setLocationId(e.target.value)} style={field}>
                  {settlements.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
              <div style={{ marginBottom: 12 }}>
                <label style={label}>Description</label>
                <textarea rows={4} value={description} onChange={(e) => setDescription(e.target.value)} required minLength={5} maxLength={1000}
                  placeholder="What do you see? Water depth, damaged bridge/road, people affected…" style={{ ...field, fontFamily: 'inherit', resize: 'vertical' }} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
                <div>
                  <label style={label}>Severity</label>
                  <select value={severity} onChange={(e) => setSeverity(e.target.value)} style={field}>
                    {['LOW', 'MODERATE', 'HIGH', 'CRITICAL'].map((s) => <option key={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label style={label}>Reporter type</label>
                  <select value={reporterType} onChange={(e) => setReporterType(e.target.value)} style={field}>
                    <option value="CITIZEN">Citizen</option>
                    <option value="WARD_OFFICER">Ward officer</option>
                    <option value="FIRST_RESPONDER">First responder</option>
                  </select>
                </div>
              </div>
              <div style={{ marginBottom: 14 }}>
                <label style={label}>Timestamp</label>
                <input type="datetime-local" value={timestamp} onChange={(e) => setTimestamp(e.target.value)} style={field} />
              </div>
              <button type="submit" disabled={submitting} className="btn btn-primary" style={{ width: '100%', justifyContent: 'center', padding: 10, fontSize: 13 }}>
                {submitting ? <Loader2 size={14} className="spin" /> : <Send size={14} />}
                <span>{submitting ? 'Extracting with AI…' : 'Submit report & recalculate'}</span>
              </button>
            </form>

            <div style={{ marginTop: 14, padding: '10px 12px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: 11, color: '#475569', lineHeight: 1.45 }}>
              <b>Verification rule:</b> a citizen report of a blocked road marks it <b>AT RISK</b> (pending verification). Ward-officer or first-responder reports mark it <b>BLOCKED</b>. The LLM never changes risk, priority or routes itself.
            </div>
          </div>
        </div>

        <div>
          {last && (
            <div className="panel-card" style={{ border: '2px solid #3b82f6', background: '#eff6ff', marginBottom: 20 }}>
              <div className="panel-header" style={{ background: '#dbeafe' }}>
                <div className="panel-title" style={{ color: '#1e40af' }}><Sparkles size={16} /><span>AI extraction — {last.id}</span></div>
                <span style={{ fontSize: 11, background: '#2563eb', color: '#fff', fontWeight: 800, padding: '2px 8px', borderRadius: 12 }}>CONFIDENCE {pct(last.extractedInfo.confidence)}</span>
              </div>
              <div className="panel-body">
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, fontSize: 12 }}>
                  {[['Location', last.extractedInfo.location], ['Severity', last.extractedInfo.severity], ['Road status', last.extractedInfo.roadStatus], ['Infrastructure', last.extractedInfo.infrastructure]].map(([k, v]) => (
                    <div key={k} style={{ background: '#fff', padding: '8px 10px', borderRadius: 6, border: '1px solid #bfdbfe' }}>
                      <div style={{ color: '#64748b', fontSize: 10, textTransform: 'uppercase' }}>{k}</div>
                      <b style={{ color: v === 'BLOCKED' ? '#dc2626' : '#0f172a' }}>{v}</b>
                    </div>
                  ))}
                </div>
                <div style={{ fontSize: 11, color: '#475569', marginTop: 8 }}>Extractor: {last.extractedInfo.source}</div>
                {last.roadAction && <div style={{ marginTop: 8, fontSize: 12, fontWeight: 700, color: '#9a3412' }}>🚧 {last.roadAction}</div>}
                <div style={{ marginTop: 10, background: '#fff', padding: 10, borderRadius: 6, border: '1px solid #bfdbfe' }}>
                  <div style={{ fontSize: 11, fontWeight: 700, marginBottom: 6 }}>Downstream changes triggered:</div>
                  {last.downstreamChanges.length === 0 ? <div style={{ fontSize: 11, color: '#64748b' }}>Evidence recorded; no ranking or route changed.</div> :
                    last.downstreamChanges.map((c, i) => (
                      <div key={i} style={{ display: 'flex', gap: 8, fontSize: 11, marginBottom: 3 }}>
                        <span style={{ minWidth: 64, fontSize: 9, fontWeight: 800, color: '#fff', background: STAGE_COLORS[c.stage], padding: '1px 5px', borderRadius: 3, textAlign: 'center' }}>{c.stage}</span>
                        <span>{c.text}</span>
                      </div>
                    ))}
                </div>
              </div>
            </div>
          )}

          <div className="panel-card">
            <div className="panel-header">
              <div className="panel-title"><CheckCircle size={16} color="#16a34a" /><span>Field reports ({systemState.reports.length})</span></div>
              <span style={{ fontSize: 11, color: '#64748b' }}>Latest first</span>
            </div>
            <div className="panel-body">
              {systemState.reports.map((rep) => (
                <div key={rep.id} style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: '10px 12px', marginBottom: 10 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 10, background: '#0f172a', color: '#fff', padding: '2px 6px', borderRadius: 4, fontFamily: 'monospace' }}>{rep.id}</span>
                      <strong style={{ fontSize: 13 }}>{rep.location}</strong>
                      {rep.status === 'REPLAYED' && <span style={{ fontSize: 9, background: '#dc2626', color: '#fff', padding: '1px 5px', borderRadius: 3, fontWeight: 800 }}>REPLAYED</span>}
                    </div>
                    <span style={{ fontSize: 11, color: '#64748b' }}>{rep.severity} · {rep.reporterType.replace('_', ' ').toLowerCase()} · {fmtAgo(rep.timestamp)}</span>
                  </div>
                  <p style={{ fontSize: 12, color: '#334155', margin: '6px 0' }}>"{rep.description}"</p>
                  <div style={{ display: 'flex', gap: 12, fontSize: 11, color: '#64748b', background: '#f8fafc', padding: '5px 10px', borderRadius: 6, flexWrap: 'wrap' }}>
                    <span>Infra: <b>{rep.extractedInfo.infrastructure}</b></span>
                    <span>Road: <b style={{ color: rep.extractedInfo.roadStatus === 'BLOCKED' ? '#dc2626' : '#16a34a' }}>{rep.extractedInfo.roadStatus}</b></span>
                    <span>Confidence: <b>{pct(rep.extractedInfo.confidence)}</b></span>
                    {rep.linkedRoadId && <span>Linked road: <b>{rep.linkedRoadId}</b></span>}
                    <span>Source: {rep.extractedInfo.source}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
