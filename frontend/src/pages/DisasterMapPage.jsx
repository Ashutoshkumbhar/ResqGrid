import React, { useState } from 'react';
import { Compass, Users, Mountain, Droplets, CloudRain } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import MapView from '../components/MapView';
import { RISK_COLORS, riskBadgeClass, pct } from '../utils';

export function FactorBars({ factors, color }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      {factors.map((f) => (
        <div key={f.key} style={{ display: 'grid', gridTemplateColumns: '130px 1fr 60px', gap: 8, alignItems: 'center', fontSize: 11 }}>
          <span style={{ color: '#334155' }} title={f.detail || f.why}>{f.label}</span>
          <div style={{ background: '#f1f5f9', height: 8, borderRadius: 4, overflow: 'hidden' }}>
            <div style={{ width: `${(f.points / f.maxPoints) * 100}%`, height: '100%', background: color, transition: 'width .4s' }} />
          </div>
          <span style={{ fontFamily: 'monospace', textAlign: 'right' }}>{f.points}/{f.maxPoints}</span>
        </div>
      ))}
    </div>
  );
}

function Metric({ Icon, label, value, color }) {
  return (
    <div style={{ background: '#f8fafc', padding: 10, borderRadius: 8, border: '1px solid #e2e8f0' }}>
      <div style={{ fontSize: 11, color: '#64748b', display: 'flex', alignItems: 'center', gap: 4 }}><Icon size={12} />{label}</div>
      <div style={{ fontSize: 15, fontWeight: 800, marginTop: 2, color }}>{value}</div>
    </div>
  );
}

export default function DisasterMapPage({ systemState }) {
  const settlements = systemState.settlements;
  const [selectedId, setSelectedId] = useState(settlements[0]?.id);
  const [forecastHour, setForecastHour] = useState(0);
  const s = settlements.find((x) => x.id === selectedId) || settlements[0];
  const rec = systemState.recommendations.find((r) => r.settlementId === s?.id);
  const forecastBySettlement = systemState.forecast?.settlements || {};
  const selectedForecast = forecastBySettlement[s?.id] || { riskByHour: [] };
  const evacuationPlan = systemState.evacuationPlans?.[s?.id];
  const forecastPoint = selectedForecast.riskByHour.find((p) => p.hour === forecastHour) || selectedForecast.riskByHour[selectedForecast.riskByHour.length - 1] || { riskStatus: s?.riskStatus, riskScore: s?.riskScore };
  const forecastLeadText = selectedForecast.firstCriticalHour !== null && selectedForecast.firstCriticalHour !== undefined
    ? `Critical in ~${selectedForecast.firstCriticalHour}h`
    : selectedForecast.firstHighHour !== null && selectedForecast.firstHighHour !== undefined
      ? `High in ~${selectedForecast.firstHighHour}h`
      : 'No high-risk threshold in next 24h';

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', height: 'calc(100vh - 128px)', overflow: 'hidden' }}>
      <div style={{ position: 'relative' }}>
        <MapView systemState={systemState} onSelectSettlement={setSelectedId} focusSettlementId={s?.id} forecastHour={forecastHour} height="100%" />
        <div style={{ position: 'absolute', top: 16, left: 60, zIndex: 400, background: 'rgba(15,23,42,0.9)', color: '#fff', padding: '8px 14px', borderRadius: 8, fontSize: 12, display: 'flex', gap: 12 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 700 }}><Compass size={14} color="#38bdf8" />{systemState.district.districtName}</span>
          <span style={{ color: '#94a3b8' }}>{settlements.length} settlements · {systemState.roads.length} roads · {systemState.kpi.blockedRoads} blocked</span>
        </div>
        <div style={{ position: 'absolute', right: 22, bottom: 18, zIndex: 450, width: 220, background: 'rgba(15,23,42,0.9)', color: '#fff', borderRadius: 10, padding: '10px 12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <span style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.6px', color: '#94a3b8' }}>Forecast horizon</span>
            <span style={{ fontSize: 12, fontWeight: 700 }}>{forecastHour}h</span>
          </div>
          <input type="range" min={0} max={24} value={forecastHour} onChange={(e) => setForecastHour(Number(e.target.value))} style={{ width: '100%' }} />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#cbd5e1', marginTop: 4 }}>
            <span>Now</span>
            <span>+24h</span>
          </div>
        </div>
      </div>

      <div style={{ background: '#fff', borderLeft: '1px solid #cbd5e1', overflowY: 'auto' }}>
        {s && (
          <>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid #e2e8f0', background: '#fafafa' }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>Settlement inspector</div>
              <div style={{ fontSize: 18, fontWeight: 800, marginTop: 2 }}>{s.name}</div>
              <div style={{ display: 'flex', gap: 8, marginTop: 6, flexWrap: 'wrap' }}>
                <span className={`status-badge ${riskBadgeClass(forecastPoint.riskStatus || s.riskStatus)}`}>Risk {forecastPoint.riskScore ?? s.riskScore}/100 {forecastPoint.riskStatus || s.riskStatus}</span>
                <span style={{ fontSize: 11, background: '#eff6ff', color: '#1d4ed8', fontWeight: 700, padding: '2px 8px', borderRadius: 12 }}>Priority #{s.priorityRank} ({s.responsePriority})</span>
                <span style={{ fontSize: 11, background: '#f1f5f9', fontWeight: 700, padding: '2px 8px', borderRadius: 12 }}>Confidence {pct(s.riskConfidence)}</span>
                <span style={{ fontSize: 11, background: '#fff7ed', color: '#c2410c', fontWeight: 700, padding: '2px 8px', borderRadius: 12 }}>{forecastLeadText}</span>
              </div>
            </div>
            <div style={{ padding: '16px 20px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8, marginBottom: 14 }}>
                <Metric Icon={Users} label="Population" value={s.population.toLocaleString()} />
                <Metric Icon={Mountain} label="Elevation" value={`${s.elevation} m (${s.relativeElevation} m above river)`} />
                <Metric Icon={CloudRain} label="Rainfall 24h" value={`${s.rainfall} mm · ${s.rainfallIntensity} mm/h`} color="#0284c7" />
                <Metric Icon={Droplets} label="Water level" value={`${s.waterLevelMeters} m ${s.waterLevel}`} color={s.waterLevel === 'NORMAL' ? '#16a34a' : '#dc2626'} />
              </div>

              <div style={{ background: s.accessibility === 'OPEN' ? '#f0fdf4' : '#fef2f2', border: `1px solid ${s.accessibility === 'OPEN' ? '#86efac' : '#fca5a5'}`, padding: 10, borderRadius: 8, marginBottom: 14, fontSize: 12 }}>
                <b>Road access: {s.accessibility.replace('_', ' ')}</b>
                <div style={{ fontSize: 11, color: '#475569', marginTop: 3 }}>
                  {s.degradedRoads.length ? `Affected roads: ${s.degradedRoads.join(', ')}. ` : 'All connected roads open. '}
                  Best surface access: {s.routeFeasibility.toLowerCase()}.
                </div>
                {rec?.route && <div style={{ fontSize: 11, marginTop: 3 }}>Assigned: <b>{rec.recommendedResourceName}</b> · {rec.routeStatus.replace('_', ' ')} · ETA {rec.etaMinutes} min</div>}
              </div>

              {evacuationPlan && (
                <div style={{ background: '#ecfeff', border: '1px solid #a5f3fc', borderRadius: 8, padding: 10, marginBottom: 14, fontSize: 12 }}>
                  <div style={{ fontWeight: 800, marginBottom: 5 }}>Evacuation plan</div>
                  <div><b>{s.vulnerablePopulation || 0}</b> vulnerable residents · <b>{evacuationPlan.shelter?.name || 'No open shelter'}</b> has <b>{evacuationPlan.shelter?.freeCapacity || 0}</b> places free.</div>
                  {evacuationPlan.route && (
                    <div style={{ fontSize: 11, color: '#0f172a', marginTop: 4 }}>
                      Safest route: {evacuationPlan.route.explanation || 'Primary route to nearest shelter'} · ETA {evacuationPlan.route.etaMinutes} min
                    </div>
                  )}
                </div>
              )}

              <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6 }}>Risk score breakdown</div>
              <FactorBars factors={forecastPoint.riskFactors || s.riskFactors} color={RISK_COLORS[forecastPoint.riskStatus || s.riskStatus]} />

              {selectedForecast.riskByHour?.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 8 }}>Projected 24h risk trend</div>
                  <div style={{ width: '100%', height: 150 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={selectedForecast.riskByHour}>
                        <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
                        <XAxis dataKey="hour" tick={{ fontSize: 10 }} tickFormatter={(value) => `${value}h`} />
                        <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
                        <Tooltip formatter={(value) => [`${value}/100`, 'Risk score']} labelFormatter={(value) => `+${value}h`} />
                        <Line type="monotone" dataKey="riskScore" stroke={RISK_COLORS[forecastPoint.riskStatus || s.riskStatus]} strokeWidth={3} dot={{ r: 2 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              <div style={{ fontSize: 12, fontWeight: 700, margin: '14px 0 6px' }}>Priority breakdown</div>
              <FactorBars factors={s.priorityFactors} color="#2563eb" />
              {s.rankReason && <div style={{ fontSize: 11, color: '#64748b', fontStyle: 'italic', marginTop: 6 }}>{s.rankReason}</div>}

              <div style={{ fontSize: 12, fontWeight: 700, margin: '14px 0 6px' }}>Evidence</div>
              <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12, color: '#334155', lineHeight: 1.5 }}>
                {s.evidence.map((e, i) => <li key={i}>{e}</li>)}
                {s.evidence.length === 0 && <li>No strong flood signals</li>}
              </ul>

              <div style={{ fontSize: 11, fontWeight: 700, color: '#64748b', textTransform: 'uppercase', margin: '16px 0 8px' }}>All settlements</div>
              {settlements.map((x) => {
                const entry = forecastBySettlement[x.id];
                const stateAtHour = entry?.riskByHour?.find((p) => p.hour === forecastHour) || entry?.riskByHour?.[0] || { riskStatus: x.riskStatus, riskScore: x.riskScore };
                const lead = entry?.firstCriticalHour !== null && entry?.firstCriticalHour !== undefined
                  ? `Critical in ~${entry.firstCriticalHour}h`
                  : entry?.firstHighHour !== null && entry?.firstHighHour !== undefined
                    ? `High in ~${entry.firstHighHour}h`
                    : 'Stable';
                return (
                  <button key={x.id} onClick={() => setSelectedId(x.id)} style={{
                    width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 10px', marginBottom: 5,
                    borderRadius: 6, border: x.id === s.id ? '2px solid #2563eb' : '1px solid #e2e8f0', background: x.id === s.id ? '#eff6ff' : '#fff', cursor: 'pointer', textAlign: 'left',
                  }}>
                    <span style={{ fontSize: 12, fontWeight: 700 }}>#{x.priorityRank} {x.name}</span>
                    <span style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 2 }}>
                      <span style={{ fontSize: 11, fontWeight: 800, color: RISK_COLORS[stateAtHour.riskStatus || x.riskStatus] }}>{stateAtHour.riskScore ?? x.riskScore} {stateAtHour.riskStatus || x.riskStatus}</span>
                      <span style={{ fontSize: 9, color: '#64748b' }}>{lead}</span>
                    </span>
                  </button>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
