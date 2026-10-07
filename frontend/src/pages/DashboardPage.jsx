import React, { useState } from 'react';
import {
  AlertTriangle, Users, OctagonAlert, Bell, Truck, MapPin, ShieldCheck, CheckCircle, XCircle, Sparkles, Info, Activity, Loader2,
} from 'lucide-react';
import MapView from '../components/MapView';
import { RISK_COLORS, STAGE_COLORS, fmtTime, fmtAgo, pct, shortName, RESOURCE_ICONS, api } from '../utils';

function Kpi({ label, value, sub, color, Icon }) {
  return (
    <div className="kpi-card">
      <div className="kpi-header">
        <span className="kpi-label">{label}</span>
        <Icon className="kpi-icon" style={{ color }} />
      </div>
      <div className="kpi-value" style={{ color }}>{value}</div>
      <div className="kpi-subtext">{sub}</div>
    </div>
  );
}

function dataSourceStatus(value) {
  if (!value) return { label: 'Simulated', color: '#64748b', detail: 'Simulated' };
  if (typeof value === 'string') {
    const text = value.toLowerCase();
    if (text.includes('live') || text.includes('api')) return { label: 'Live', color: '#0f766e', detail: value };
    if (text.includes('cache') || text.includes('cached')) return { label: 'Cached', color: '#d97706', detail: value };
    return { label: 'Simulated', color: '#64748b', detail: value };
  }
  const status = String(value.status || value.label || 'Simulated').toUpperCase();
  if (status.includes('LIVE')) return { label: 'Live', color: '#0f766e', detail: value.detail || value.label || 'Live' };
  if (status.includes('CACHED')) return { label: 'Cached', color: '#d97706', detail: value.detail || value.label || 'Cached' };
  return { label: 'Simulated', color: '#64748b', detail: value.detail || value.label || 'Simulated' };
}

export function RouteStatusCard({ rec }) {
  const route = rec.route;
  if (!route) return null;
  const esc = rec.routeStatus === 'ESCALATION_REQUIRED';
  const rerouted = route.originalRouteStatus === 'INVALID';
  return (
    <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 10, marginBottom: 10, background: '#fff' }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: '#0f172a', marginBottom: 6 }}>
        {RESOURCE_ICONS[rec.recommendedResourceType] || '⚠️'} {route.resourceName} → {shortName(route.targetSettlementName)}
      </div>
      <div className={`route-card ${rerouted ? 'invalid' : 'valid'}`} style={{ marginBottom: 6 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, fontWeight: 700 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            {rerouted ? <XCircle size={14} color="#dc2626" /> : <CheckCircle size={14} color="#16a34a" />}
            Original route: {route.originalRoadIds.join(' → ')}
          </span>
          <b style={{ color: rerouted ? '#dc2626' : '#16a34a' }}>{rerouted ? '❌ INVALID' : '✓ VALID'}</b>
        </div>
        {rerouted && <div style={{ fontSize: 11, color: '#991b1b', marginTop: 3 }}>Blocked: {route.blockedRoadsOnPath.join(', ')}</div>}
      </div>
      {rerouted && !esc && (
        <div className="route-card alt" style={{ marginBottom: 6 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, fontWeight: 700, color: '#1d4ed8' }}>
            <span>Alternative route: {route.alternativeRoadIds.join(' → ')}</span>
            <b>✓ VALID</b>
          </div>
        </div>
      )}
      {esc && (
        <div style={{ background: '#7f1d1d', color: '#fff', padding: '6px 10px', borderRadius: 6, fontSize: 11, fontWeight: 700 }}>
          NO VALID ROUTE → ESCALATION REQUIRED
        </div>
      )}
      {!esc && (
        <div style={{ fontSize: 11, color: '#475569', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <span>{route.distanceKm} km</span>
          <span>ETA {route.etaMinutes} min</span>
          {route.atRiskRoadsOnPath?.length > 0 && <span style={{ color: '#d97706' }}>⚠ At risk: {route.atRiskRoadsOnPath.join(', ')}</span>}
          {route.osrmCheck && (
            <span title="Street-level estimate from the public OSRM router through the same waypoints">
              OSRM check: {route.osrmCheck.distanceKm} km / {Math.round(route.osrmCheck.durationMin)} min{route.osrmCheck.consistent ? '' : ' (street path differs)'}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

export function ChangeLog({ entry, compact = false }) {
  if (!entry) return null;
  return (
    <div>
      <div style={{ fontSize: 12, fontWeight: 700, color: '#0f172a', marginBottom: 6 }}>
        {entry.title} <span style={{ color: '#64748b', fontWeight: 500 }}>· {fmtTime(entry.timestamp)}</span>
      </div>
      {entry.changes.length === 0 ? (
        <div style={{ fontSize: 11, color: '#64748b' }}>No downstream decision changed.</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {entry.changes.slice(0, compact ? 6 : 50).map((c, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'baseline', fontSize: 11 }}>
              <span style={{ minWidth: 64, fontSize: 9, fontWeight: 800, color: '#fff', background: STAGE_COLORS[c.stage], padding: '1px 5px', borderRadius: 3, textAlign: 'center' }}>{c.stage}</span>
              <span style={{ color: '#334155' }}>{c.text}</span>
            </div>
          ))}
          {compact && entry.changes.length > 6 && <div style={{ fontSize: 11, color: '#64748b' }}>+{entry.changes.length - 6} more</div>}
        </div>
      )}
    </div>
  );
}

export function ExplainPanel({ systemState, actions, busy, settlementId }) {
  const [result, setResult] = useState(null);
  const onExplain = async () => {
    const data = await actions.explain(settlementId);
    if (data) setResult(data);
  };
  const text = result?.text || systemState?.aiExplanation;
  return (
    <div className="panel-card" style={{ border: '1px solid #c7d2fe', background: '#f5f3ff' }}>
      <div className="panel-header" style={{ background: '#ede9fe', borderBottom: '1px solid #ddd6fe' }}>
        <div className="panel-title" style={{ color: '#5b21b6' }}>
          <Sparkles size={16} style={{ color: '#7c3aed' }} />
          <span>Explain in plain words</span>
        </div>
        <button className="btn btn-primary" style={{ fontSize: 11, padding: '4px 10px', background: '#7c3aed' }} onClick={onExplain} disabled={busy === 'explain'}>
          {busy === 'explain' ? <Loader2 size={12} className="spin" /> : <Sparkles size={12} />} Explain decision
        </button>
      </div>
      <div className="panel-body">
        <p style={{ fontSize: 12, color: '#3730a3', lineHeight: 1.55 }}>{text}</p>
        <div style={{ marginTop: 8, fontSize: 10, color: '#6d28d9', display: 'flex', alignItems: 'flex-start', gap: 4 }}>
          <Info size={12} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>
            {result?.source?.startsWith('GEMINI') ? 'Written by AI using only system data.' : 'Written from system data.'} Decisions are made by the system, not the AI.
          </span>
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage({ systemState, actions, busy, demoNarrations = [] }) {
  const [selectedId, setSelectedId] = useState(null);
  const [alertLanguage, setAlertLanguage] = useState('en');
  const [previewText, setPreviewText] = useState('');
  const [previewBusy, setPreviewBusy] = useState(false);
  const kpi = systemState.kpi;
  const settlements = systemState.settlements || [];
  const recommendations = systemState.recommendations || [];
  const alerts = systemState.alerts || [];
  const alertHistory = systemState.alertHistory || [];
  const blockedIds = systemState.roads.filter((r) => r.status === 'BLOCKED').map((r) => r.id);
  const dataSourceEntries = Object.entries(systemState.dataSources || {});
  const recentNarration = demoNarrations[demoNarrations.length - 1];
  const priorityChangeNames = new Set(
    (systemState.lastChange?.changes || []).filter((c) => c.stage === 'PRIORITY').map((c) => c.text.split(':')[0])
  );

  const previewAlert = async () => {
    if (!selectedId) {
      setPreviewText('Select a settlement first to preview its alert message.');
      return;
    }
    setPreviewBusy(true);
    try {
      const payload = await api('/api/alerts/send', { settlementId: selectedId, language: alertLanguage, preview: true }, 'POST');
      setPreviewText(payload.message || 'Preview unavailable.');
    } catch (err) {
      setPreviewText(`Preview unavailable: ${err.message}`);
    } finally {
      setPreviewBusy(false);
    }
  };

  return (
    <div style={{ padding: '20px 24px' }}>
      {demoNarrations.length > 0 && (
        <div className="demo-banner">
          <div className="demo-banner-header">
            <span className="demo-badge">Run Demo</span>
            <span className="demo-meta">Story timeline</span>
          </div>
          <div className="demo-timeline">
            {demoNarrations.slice(-4).map((msg, idx) => (
              <div key={`${msg}-${idx}`} className="demo-story-item">{msg}</div>
            ))}
          </div>
          {recentNarration && <div className="demo-live">Latest: {recentNarration}</div>}
        </div>
      )}

      <div className="kpi-grid">
        <Kpi label="Critical Areas" value={kpi.criticalAreas} sub={`${settlements.filter((s) => s.riskStatus === 'HIGH').length} more at HIGH risk`} color="#dc2626" Icon={AlertTriangle} />
        <Kpi label="People at Risk" value={kpi.affectedPopulation.toLocaleString()} sub="In HIGH / CRITICAL settlements" color="#ea580c" Icon={Users} />
        <Kpi label="Blocked Roads" value={kpi.blockedRoads} sub={blockedIds.length ? `${blockedIds.join(', ')} · ${kpi.atRiskRoads} at risk` : `${kpi.atRiskRoads} road(s) at risk`} color={kpi.blockedRoads ? '#dc2626' : '#10b981'} Icon={OctagonAlert} />
        <Kpi label="Active Warnings" value={kpi.activeWarnings} sub="Flood, route & escalation alerts" color="#dc2626" Icon={Bell} />
        <Kpi label="Units Available" value={kpi.availableResources} sub={`of ${systemState.resources.length} district resources`} color="#16a34a" Icon={Truck} />
      </div>

      <div className="dashboard-grid">
        <div>
          <div className="panel-card">
            <div className="panel-header">
              <div className="panel-title">
                <MapPin size={16} style={{ color: '#2563eb' }} />
                <span>GIS Response Map — {systemState.district.districtName}</span>
              </div>
              <span style={{ fontSize: 11, color: '#64748b' }}>Updated {fmtTime(kpi.lastUpdated)} · click a settlement</span>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, padding: '8px 12px 0', alignItems: 'center' }}>
              {dataSourceEntries.map(([layer, value]) => {
                const meta = dataSourceStatus(value);
                return (
                  <span key={layer} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 8px', borderRadius: 999, background: '#eff6ff', color: '#1e3a8a', fontSize: 10, fontWeight: 800, border: '1px solid #bfdbfe' }}>
                    <span style={{ width: 7, height: 7, borderRadius: '50%', background: meta.color, display: 'inline-block' }} />
                    {layer}: {meta.label}
                  </span>
                );
              })}
            </div>
            <MapView systemState={systemState} onSelectSettlement={setSelectedId} focusSettlementId={selectedId} height="460px" />
          </div>

          {systemState.lastChange && (
            <div className="panel-card" style={{ border: '2px solid #2563eb' }}>
              <div className="panel-header" style={{ background: '#eff6ff' }}>
                <div className="panel-title" style={{ color: '#1e40af' }}>
                  <Activity size={16} />
                  <span>What just changed</span>
                </div>
                <span style={{ fontSize: 11, color: '#1e40af', fontWeight: 700 }}>{systemState.lastChange.changes.length} downstream change(s)</span>
              </div>
              <div className="panel-body">
                <ChangeLog entry={systemState.lastChange} compact />
              </div>
            </div>
          )}

          <div className="panel-card">
            <div className="panel-header">
              <div className="panel-title">
                <AlertTriangle size={16} style={{ color: '#dc2626' }} />
                <span>Alerts</span>
              </div>
              <span style={{ fontSize: 11, background: '#fee2e2', color: '#dc2626', padding: '2px 8px', borderRadius: 12, fontWeight: 700 }}>{alerts.length} ACTIVE</span>
            </div>
            <div className="panel-body">
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
                <label htmlFor="alert-language" style={{ fontSize: 12, fontWeight: 700, color: '#334155' }}>Language</label>
                <select id="alert-language" value={alertLanguage} onChange={(e) => setAlertLanguage(e.target.value)} style={{ borderRadius: 6, padding: '6px 8px', border: '1px solid #cbd5e1' }}>
                  <option value="en">English</option>
                  <option value="hi">हिन्दी</option>
                  <option value="mr">मराठी</option>
                </select>
                <button className="btn btn-primary" style={{ fontSize: 11, padding: '6px 10px' }} onClick={previewAlert} disabled={previewBusy || !selectedId}>
                  {previewBusy ? <Loader2 size={12} className="spin" /> : 'Preview message'}
                </button>
              </div>
              {previewText && (
                <div style={{ padding: '10px 12px', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 8, marginBottom: 12, color: '#1e3a8a', fontSize: 12, lineHeight: 1.55 }}>
                  {previewText}
                </div>
              )}
              {alerts.length === 0 && <div style={{ textAlign: 'center', padding: 24, color: '#64748b' }}>No active warnings.</div>}
              {alerts.map((al) => {
                const critical = al.severity === 'CRITICAL';
                return (
                  <div key={al.id} style={{ background: critical ? '#fef2f2' : '#fff7ed', border: `1px solid ${critical ? '#fca5a5' : '#fdba74'}`, borderRadius: 8, padding: '12px 14px', marginBottom: 10 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 800, color: critical ? '#991b1b' : '#9a3412' }}>
                          {al.type === 'ESCALATION_REQUIRED' ? '⛔' : al.type === 'ROUTE_INVALIDATED' ? '🚧' : critical ? '🔴' : '🟠'} {al.title}
                        </div>
                        <p style={{ fontSize: 12, color: '#334155', marginTop: 3 }}>{al.message}</p>
                      </div>
                      <div style={{ textAlign: 'right', minWidth: 84 }}>
                        <div style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>Confidence</div>
                        <div style={{ fontSize: 18, fontWeight: 800, fontFamily: 'monospace' }}>{pct(al.confidence)}</div>
                      </div>
                    </div>
                    <details style={{ marginTop: 6 }}>
                      <summary style={{ fontSize: 11, color: '#2563eb', cursor: 'pointer' }}>Evidence ({al.evidence.length})</summary>
                      <ul className="evidence-list">
                        {al.evidence.map((ev, i) => (
                          <li key={i} className="evidence-item"><span className="evidence-check">✓</span><span>{ev}</span></li>
                        ))}
                      </ul>
                    </details>
                    <div style={{ marginTop: 8, display: 'flex', justifyContent: 'space-between', background: 'rgba(255,255,255,0.7)', padding: '6px 10px', borderRadius: 6, fontSize: 12 }}>
                      <span><b>Recommended action:</b> <span style={{ color: '#2563eb', fontWeight: 700 }}>{al.recommendedAction}</span></span>
                      <span style={{ fontSize: 10, color: '#64748b' }} title={al.timestamp}>raised {fmtAgo(al.timestamp)}</span>
                    </div>
                  </div>
                );
              })}
              {alertHistory.length > 0 && (
                <div style={{ marginTop: 12, borderTop: '1px solid #e2e8f0', paddingTop: 12 }}>
                  <div style={{ fontSize: 12, fontWeight: 800, color: '#0f172a', marginBottom: 8 }}>Sent history</div>
                  {alertHistory.slice(0, 4).map((item, idx) => (
                    <div key={`${item.sentAt || idx}-${item.settlementId || idx}`} style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: '8px 10px', marginBottom: 8 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, marginBottom: 4 }}>
                        <strong style={{ fontSize: 12 }}>{item.settlementName || item.settlementId}</strong>
                        <span style={{ fontSize: 10, color: '#64748b' }}>{item.language || 'en'}</span>
                      </div>
                      <div style={{ fontSize: 11, color: '#334155', lineHeight: 1.5 }}>{item.message}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        <div>
          <div className="panel-card">
            <div className="panel-header">
              <div className="panel-title">
                <ShieldCheck size={16} style={{ color: '#2563eb' }} />
                <span>Who needs help first</span>
              </div>
              
            </div>
            <div className="panel-body" style={{ padding: 12 }}>
              <p style={{ fontSize: 11, color: '#64748b', marginBottom: 10 }}>
                Ranked by flood risk, people affected, field reports, road access and whether help is already there.
              </p>
              {settlements.map((s) => {
                const nameChanged = priorityChangeNames.has(s.name);
                const riskChanged = systemState.lastChange?.changes?.some((c) => c.text.includes(s.name) && c.stage === 'RISK');
                return (
                  <div key={s.id} onClick={() => setSelectedId(s.id)} className={nameChanged ? 'priority-card priority-flash' : 'priority-card'} style={{
                    cursor: 'pointer', background: s.priorityRank === 1 ? '#eff6ff' : '#fff',
                    border: `1px solid ${selectedId === s.id ? '#2563eb' : s.priorityRank === 1 ? '#bfdbfe' : '#e2e8f0'}`,
                    borderRadius: 8, padding: '9px 12px', marginBottom: 8,
                  }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ background: s.priorityRank === 1 ? '#2563eb' : '#64748b', color: '#fff', fontWeight: 800, fontSize: 11, padding: '2px 6px', borderRadius: 4 }}>#{s.priorityRank}</span>
                      <strong style={{ fontSize: 13 }}>{s.name}</strong>
                    </div>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 11 }}>
                      <span className={riskChanged ? 'risk-badge risk-flash' : 'risk-badge'} style={{ color: RISK_COLORS[s.riskStatus], fontWeight: 700 }}>Risk {s.riskScore}</span>
                      <b style={{ fontSize: 14, fontFamily: 'monospace', color: '#1d4ed8' }}>{s.responsePriority}</b>
                    </div>
                  </div>
                  {s.priorityRank <= 3 && (
                    <details style={{ marginTop: 6, fontSize: 11, color: '#475569' }} onClick={(e) => e.stopPropagation()}>
                      <summary style={{ fontWeight: 600, color: '#2563eb', cursor: 'pointer' }}>Why #{s.priorityRank}?</summary>
                      <ul style={{ margin: '2px 0 0 16px', padding: 0, listStyle: 'none' }}>
                        {s.priorityWhy.map((w, i) => <li key={i}>✓ {w}</li>)}
                      </ul>
                      {s.rankReason && <div style={{ marginTop: 3, fontStyle: 'italic', color: '#64748b' }}>{s.rankReason}</div>}
                    </details>
                  )}
                </div>
                );
              })}
            </div>
          </div>

          <div className="panel-card">
            <div className="panel-header">
              <div className="panel-title">
                <Truck size={16} style={{ color: '#16a34a' }} />
                <span>Rescue plan</span>
              </div>
              <span style={{ fontSize: 10, color: '#64748b' }}>Final decision stays with the operator</span>
            </div>
            <div className="panel-body">
              {recommendations.map((rec) => (
                <div key={rec.settlementId} style={{ marginBottom: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
                    <span style={{ fontSize: 12, fontWeight: 800 }}>#{rec.priorityRank} {shortName(rec.settlementName)} → {rec.recommendedResourceName || 'ESCALATE'}</span>
                    <span style={{ fontSize: 11, color: '#64748b' }}>confidence {pct(rec.confidenceScore)}</span>
                  </div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: { VALID: '#16a34a', ALTERNATIVE_VALID: '#d97706', ESCALATION_REQUIRED: '#dc2626' }[rec.routeStatus] }}>
                    {{ VALID: `Route open · ${rec.etaMinutes} min`, ALTERNATIVE_VALID: `Main road closed — using another route · ${rec.etaMinutes} min`, ESCALATION_REQUIRED: rec.recommendedAction }[rec.routeStatus]}
                  </div>
                  <details style={{ marginTop: 4 }}>
                    <summary style={{ fontSize: 11, color: '#2563eb', cursor: 'pointer' }}>Details</summary>
                    {rec.route && <RouteStatusCard rec={rec} />}
                    <ul style={{ margin: '0 0 0 16px', padding: 0, fontSize: 11, color: '#334155' }}>
                      {rec.whySelected.map((w, i) => <li key={i}>{w}</li>)}
                    </ul>
                  </details>
                </div>
              ))}
            </div>
          </div>

          <ExplainPanel systemState={systemState} actions={actions} busy={busy} settlementId={selectedId || recommendations[0]?.settlementId} />
        </div>
      </div>
    </div>
  );
}
