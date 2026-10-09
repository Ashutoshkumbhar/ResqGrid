import React, { useState } from 'react';
import { Home, Truck, OctagonAlert, Navigation, Loader2, Route } from 'lucide-react';
import { RouteStatusCard } from './DashboardPage';
import { RESOURCE_ICONS, ROAD_COLORS, pct, shortName } from '../utils';

const SCENARIOS = [
  { n: 1, title: 'Scenario 1 — All roads open', expect: 'Route → VALID', color: '#16a34a' },
  { n: 2, title: 'Scenario 2 — Primary road blocked', expect: 'Original INVALID → alternative generated', color: '#d97706' },
  { n: 3, title: 'Scenario 3 — Multiple roads blocked', expect: 'No valid route → ESCALATION', color: '#dc2626' },
];

const STATUS_COLORS = { AVAILABLE: ['#dcfce7', '#166534'], DEPLOYED: ['#dbeafe', '#1e40af'], BUSY: ['#fef3c7', '#92400e'], UNAVAILABLE: ['#e2e8f0', '#334155'] };

export default function ResourcesRoutesPage({ systemState, actions, busy }) {
  const settlements = [...systemState.settlements].sort((a, b) => a.id.localeCompare(b.id));
  const [targetId, setTargetId] = useState('S1');
  const [scenario, setScenario] = useState(null);
  const [result, setResult] = useState(null);
  const recs = systemState.recommendations;
  const evacuationPlans = settlements.map((s) => ({
    settlement: s,
    plan: systemState.evacuationPlans?.[s.id],
    rec: recs.find((r) => r.settlementId === s.id),
  }));

  const runScenario = async (n, apply = false) => {
    setScenario(n);
    const data = await actions.scenario(targetId, n, apply);
    if (data) setResult(data);
  };

  return (
    <div style={{ padding: 24, maxWidth: 1280, margin: '0 auto' }}>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 24, fontWeight: 800, margin: 0 }}>Resources & Routes</h1>
        <p style={{ fontSize: 13, color: '#64748b', marginTop: 4 }}>
          Shortest-path routing on the district road graph (NetworkX). Blocked roads are removed, at-risk roads penalised; OSRM gives a street-level ETA cross-check.
        </p>
      </div>

      <div className="panel-card" style={{ border: '2px solid #2563eb' }}>
        <div className="panel-header" style={{ background: '#eff6ff' }}>
          <div className="panel-title" style={{ color: '#1e40af' }}><Navigation size={18} /><span>Route validity testing</span></div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
            <span>Target:</span>
            <select value={targetId} onChange={(e) => { setTargetId(e.target.value); setResult(null); setScenario(null); }} style={{ padding: '4px 8px', borderRadius: 6, border: '1px solid #cbd5e1' }}>
              {settlements.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
        </div>
        <div className="panel-body">
          <p style={{ fontSize: 12, color: '#334155', marginBottom: 12 }}>
            Each test runs on a copy of the road network from every available unit to the target. "Apply to live map" pushes the scenario's closures into the live system so the whole response loop updates.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12, marginBottom: 14 }}>
            {SCENARIOS.map((sc) => (
              <div key={sc.n} style={{ border: scenario === sc.n ? `2px solid ${sc.color}` : '1px solid #cbd5e1', borderRadius: 8, padding: 12, background: '#fff' }}>
                <b style={{ fontSize: 13 }}>{sc.title}</b>
                <div style={{ fontSize: 11, color: '#64748b', margin: '4px 0 10px' }}>Expected: {sc.expect}</div>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button className="btn btn-secondary" style={{ fontSize: 11, padding: '4px 10px' }} onClick={() => runScenario(sc.n)} disabled={!!busy}>
                    {busy === `scenario-${sc.n}` && <Loader2 size={12} className="spin" />} Run test
                  </button>
                  <button className="btn btn-primary" style={{ fontSize: 11, padding: '4px 10px' }} onClick={() => runScenario(sc.n, true)} disabled={!!busy}>Apply to live map</button>
                </div>
              </div>
            ))}
          </div>

          {result?.route && (
            <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: 14 }}>
              <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 6 }}>
                {result.scenarioLabel}: {result.blockedRoads.length ? `blocked ${result.blockedRoads.join(', ')}` : 'no closures'} {result.applied && <span style={{ color: '#2563eb' }}>· applied to live map</span>}
              </div>
              <RouteStatusCard rec={{ route: result.route, routeStatus: result.route.escalationRequired ? 'ESCALATION_REQUIRED' : 'VALID', recommendedResourceType: null }} />
              <div style={{ fontSize: 12, background: '#fff', border: '1px solid #cbd5e1', borderRadius: 6, padding: 10 }}>
                <b>Route engine:</b> {result.route.explanation}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="panel-card">
        <div className="panel-header">
          <div className="panel-title"><Truck size={16} color="#16a34a" /><span>Resource recommendations (current plan)</span></div>
          <span style={{ fontSize: 11, color: '#64748b' }}>Recommendation — final decision stays with the operator</span>
        </div>
        <div className="panel-body" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 16 }}>
          {recs.map((rec) => (
            <div key={rec.settlementId} style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 12 }}>
              <div style={{ fontSize: 11, color: '#64748b' }}>TARGET · priority #{rec.priorityRank} · risk {rec.riskScore} · {rec.population.toLocaleString()} people</div>
              <div style={{ fontSize: 15, fontWeight: 800, margin: '2px 0 8px' }}>{rec.settlementName}</div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 6, padding: '8px 10px', marginBottom: 8 }}>
                <div>
                  <div style={{ fontSize: 10, color: '#166534', fontWeight: 700 }}>RECOMMENDED RESOURCE</div>
                  <div style={{ fontSize: 14, fontWeight: 800 }}>{RESOURCE_ICONS[rec.recommendedResourceType] || '⚠️'} {rec.recommendedResourceName || 'Escalate'}</div>
                </div>
                <div style={{ textAlign: 'right', fontSize: 12 }}>
                  {rec.etaMinutes != null && <div><b>{rec.distanceKm} km · ETA {rec.etaMinutes} min</b></div>}
                  <div style={{ color: '#64748b' }}>confidence {pct(rec.confidenceScore)}</div>
                </div>
              </div>
              {rec.route && <RouteStatusCard rec={rec} />}
              <div style={{ fontSize: 11, fontWeight: 700, marginBottom: 3 }}>Why this resource?</div>
              <ul style={{ margin: '0 0 8px 16px', padding: 0, fontSize: 11 }}>{rec.whySelected.map((w, i) => <li key={i}>{w}</li>)}</ul>
              {rec.candidatesConsidered.length > 0 && (
                <table style={{ width: '100%', fontSize: 10, borderCollapse: 'collapse', marginBottom: 8 }}>
                  <thead><tr style={{ color: '#64748b', textAlign: 'left' }}><th>Considered</th><th>ETA</th><th>Score</th><th>Note</th></tr></thead>
                  <tbody>
                    {rec.candidatesConsidered.map((c) => (
                      <tr key={c.resourceId} style={{ borderTop: '1px solid #f1f5f9', fontWeight: c.resourceId === rec.recommendedResourceId ? 700 : 400 }}>
                        <td>{c.resourceName}</td><td>{c.etaMinutes ?? '—'} min</td><td>{c.score ?? '—'}</td><td>{c.note}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {rec.nearestShelter && <div style={{ fontSize: 11, color: '#475569' }}>🏠 Nearest shelter: {rec.nearestShelter.name} ({rec.nearestShelter.distanceKm} km)</div>}
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10 }}>
                {rec.recommendedResourceId && (
                  <button className="btn btn-primary" style={{ fontSize: 11, padding: '4px 10px' }} disabled={!!busy}
                    onClick={() => actions.resourceStatus(rec.recommendedResourceId, 'DEPLOYED', rec.settlementId)}>
                    Mark {rec.recommendedResourceName} as deployed
                  </button>
                )}
                {rec.recommendedResourceId && (
                  <button className="btn btn-secondary" style={{ fontSize: 11, padding: '4px 10px' }} disabled={!!busy}
                    onClick={async () => {
                      const payload = { settlementId: rec.settlementId, decision: 'APPROVE', resourceId: rec.recommendedResourceId, reason: 'Operator approved the recommended dispatch.' };
                      await actions.resourceStatus(rec.recommendedResourceId, 'DEPLOYED', rec.settlementId);
                      await fetch('/api/resources/decision', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
                    }}>
                    Approve
                  </button>
                )}
                <button className="btn btn-secondary" style={{ fontSize: 11, padding: '4px 10px' }} disabled={!!busy}
                  onClick={async () => {
                    await fetch('/api/resources/decision', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ settlementId: rec.settlementId, decision: 'REJECT', reason: 'Operator rejected the current recommendation.' }) });
                    window.location.reload();
                  }}>
                  Reject
                </button>
                {systemState.resources.filter((resource) => resource.mobile && resource.status !== 'UNAVAILABLE').length > 0 && (
                  <select value={rec.recommendedResourceId || ''} onChange={async (e) => {
                    const targetResourceId = e.target.value;
                    if (!targetResourceId) return;
                    await fetch('/api/resources/decision', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ settlementId: rec.settlementId, decision: 'OVERRIDE', resourceId: targetResourceId, reason: 'Operator overrode the recommendation.' }) });
                    window.location.reload();
                  }} style={{ fontSize: 11, padding: '4px 8px', borderRadius: 6, border: '1px solid #cbd5e1' }}>
                    <option value="">Override…</option>
                    {systemState.resources.filter((resource) => resource.mobile && resource.status !== 'UNAVAILABLE').map((resource) => (
                      <option key={resource.id} value={resource.id}>{resource.name}</option>
                    ))}
                  </select>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="panel-card">
        <div className="panel-header">
          <div className="panel-title"><Home size={16} color="#2563eb" /><span>Evacuation plan per village</span></div>
          <span style={{ fontSize: 11, color: '#64748b' }}>Shelter, safest route, ETA and assigned response unit</span>
        </div>
        <div className="panel-body evacuation-grid">
          {evacuationPlans.map(({ settlement, plan, rec }) => {
            const route = plan?.route;
            const invalid = route?.originalRouteStatus === 'INVALID';
            const activeRoads = invalid ? route?.alternativeRoadIds : route?.originalRoadIds;
            const firstRoad = route?.originalRoadIds?.[0];
            return (
              <div key={settlement.id} className={`evac-card ${invalid ? 'changed' : ''}`}>
                <div className="evac-card-head">
                  <div>
                    <div style={{ fontSize: 11, color: '#64748b', fontWeight: 800 }}>#{settlement.priorityRank} PRIORITY</div>
                    <div style={{ fontSize: 15, fontWeight: 900 }}>{shortName(settlement.name)}</div>
                  </div>
                  <span className={`risk-badge ${settlement.riskStatus === 'CRITICAL' ? 'badge-critical' : settlement.riskStatus === 'HIGH' ? 'badge-high' : 'badge-moderate'}`}>
                    {settlement.riskStatus}
                  </span>
                </div>

                <div className="evac-metrics">
                  <div><span>Shelter</span><b>{plan?.shelter?.name || 'No shelter'}</b></div>
                  <div><span>ETA</span><b>{route?.etaMinutes != null ? `${route.etaMinutes} min` : 'Escalate'}</b></div>
                  <div><span>Free capacity</span><b>{plan?.shelter?.freeCapacity ?? 0}</b></div>
                  <div><span>Resource</span><b>{rec?.recommendedResourceName || 'Escalate'}</b></div>
                </div>

                {route ? (
                  <div className="evac-route">
                    <div className={`route-card ${invalid ? 'invalid' : 'valid'}`}>
                      <Route size={14} />
                      <span>Original: {route.originalRoadIds?.join(' -> ') || 'none'}</span>
                      <b>{invalid ? 'INVALID' : 'VALID'}</b>
                    </div>
                    {invalid && (
                      <div className="route-card alt">
                        <Route size={14} />
                        <span>Alternative: {route.alternativeRoadIds?.join(' -> ') || 'none'}</span>
                        <b>{route.alternativeRouteStatus}</b>
                      </div>
                    )}
                    <div style={{ fontSize: 11, color: '#475569' }}>
                      Safest now: <b>{activeRoads?.join(' -> ') || 'local coordination'}</b>
                      {route.blockedRoadsOnPath?.length > 0 && <span style={{ color: '#dc2626' }}> | blocked: {route.blockedRoadsOnPath.join(', ')}</span>}
                    </div>
                    {firstRoad && (
                      <button className="btn btn-secondary" style={{ marginTop: 8, fontSize: 11, padding: '5px 9px' }} disabled={!!busy} onClick={() => actions.setRoad(firstRoad, invalid ? 'OPEN' : 'BLOCKED')}>
                        {invalid ? `Reopen ${firstRoad}` : `Block ${firstRoad} and re-plan`}
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="evac-escalate">{plan?.message || 'No viable evacuation route available.'}</div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: 20 }}>
        <div className="panel-card">
          <div className="panel-header">
            <div className="panel-title"><Truck size={16} color="#16a34a" /><span>Emergency resources ({systemState.resources.length})</span></div>
          </div>
          <div className="panel-body">
            {systemState.resources.map((res) => {
              const [bg, fg] = STATUS_COLORS[res.status];
              const target = systemState.settlements.find((s) => s.id === res.currentAssignment);
              return (
                <div key={res.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '9px 12px', borderRadius: 8, border: '1px solid #e2e8f0', marginBottom: 8, gap: 8 }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700 }}>{RESOURCE_ICONS[res.type]} {res.name}</div>
                    <div style={{ fontSize: 11, color: '#64748b' }}>{res.type.replace('_', ' ')} · {res.locationName}{target ? ` · assigned to ${shortName(target.name)}` : ''}</div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 12, background: bg, color: fg }}>{res.status}</span>
                    {res.mobile && (
                      <select value="" disabled={!!busy} onChange={(e) => e.target.value && actions.resourceStatus(res.id, e.target.value, null)}
                        style={{ fontSize: 10, padding: '2px 4px', borderRadius: 4, border: '1px solid #cbd5e1' }}>
                        <option value="">Set…</option>
                        {['AVAILABLE', 'BUSY', 'UNAVAILABLE'].filter((s) => s !== res.status).map((s) => <option key={s} value={s}>{s}</option>)}
                      </select>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="panel-card">
          <div className="panel-header">
            <div className="panel-title"><OctagonAlert size={16} color="#ea580c" /><span>Road network ({systemState.roads.length})</span></div>
          </div>
          <div className="panel-body">
            {systemState.roads.map((road) => (
              <div key={road.id} style={{ padding: '8px 12px', borderRadius: 8, border: `1px solid ${road.status === 'OPEN' ? '#e2e8f0' : ROAD_COLORS[road.status]}`, marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700 }}>{road.id} · {road.name}</div>
                    <div style={{ fontSize: 11, color: '#64748b' }}>{road.sourceName} ↔ {road.destinationName} · {road.distanceKm} km{road.floodProne ? ' · flood-prone' : ''}</div>
                  </div>
                  <div style={{ display: 'flex', gap: 3 }}>
                    {['OPEN', 'AT_RISK', 'BLOCKED'].map((st) => (
                      <button key={st} disabled={!!busy} onClick={() => actions.setRoad(road.id, st)} style={{
                        fontSize: 10, fontWeight: 700, padding: '3px 7px', borderRadius: 4, cursor: 'pointer',
                        border: `1px solid ${ROAD_COLORS[st]}`, background: road.status === st ? ROAD_COLORS[st] : '#fff', color: road.status === st ? '#fff' : ROAD_COLORS[st],
                      }}>{st.replace('_', ' ')}</button>
                    ))}
                  </div>
                </div>
                <div style={{ fontSize: 10, color: '#64748b', marginTop: 3, fontStyle: 'italic' }}>{road.statusReason}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
