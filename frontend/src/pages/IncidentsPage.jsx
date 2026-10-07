import React from 'react';
import { TrendingUp, Database, History } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid, Cell } from 'recharts';
import { FactorBars } from './DisasterMapPage';
import { ChangeLog } from './DashboardPage';
import { RISK_COLORS, riskBadgeClass, pct, shortName } from '../utils';

export default function IncidentsPage({ systemState }) {
  const settlements = systemState.settlements;
  const chartData = settlements.map((s) => ({ name: shortName(s.name), risk: s.riskScore, priority: s.responsePriority, status: s.riskStatus }));

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 24, fontWeight: 800, margin: 0 }}>Incidents: Risk, Evidence & Priority</h1>
        <p style={{ fontSize: 13, color: '#64748b', marginTop: 4 }}>Explainable weighted scoring — every point of every score is traceable to an input.</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) minmax(300px, 1fr)', gap: 20, marginBottom: 20 }}>
        <div className="panel-card" style={{ margin: 0 }}>
          <div className="panel-header">
            <div className="panel-title"><TrendingUp size={16} color="#2563eb" /><span>Flood risk vs response priority</span></div>
            <span style={{ fontSize: 11, background: '#eff6ff', color: '#1d4ed8', fontWeight: 700, padding: '2px 8px', borderRadius: 4 }}>PRIORITY ≠ RISK</span>
          </div>
          <div className="panel-body" style={{ height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="risk" name="Flood risk (0-100)" radius={[4, 4, 0, 0]}>
                  {chartData.map((d) => <Cell key={d.name} fill={RISK_COLORS[d.status]} />)}
                </Bar>
                <Bar dataKey="priority" name="Response priority (0-100)" fill="#2563eb" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel-card" style={{ margin: 0 }}>
          <div className="panel-header">
            <div className="panel-title"><Database size={16} color="#0891b2" /><span>Data processing pipeline</span></div>
          </div>
          <div className="panel-body" style={{ fontSize: 11 }}>
            {systemState.processingLog.map((p, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
                <span style={{ minWidth: 70, fontWeight: 800, fontSize: 9, color: '#fff', background: '#0891b2', borderRadius: 3, padding: '2px 4px', textAlign: 'center', height: 'fit-content' }}>{p.step}</span>
                <span style={{ color: '#334155' }}>{p.detail}</span>
              </div>
            ))}
            <div style={{ borderTop: '1px solid #e2e8f0', marginTop: 8, paddingTop: 8, color: '#64748b' }}>
              {Object.entries(systemState.dataSources || {}).map(([k, v]) => {
                const detail = typeof v === 'string' ? v : (v?.detail || v?.label || 'Unknown');
                return <div key={k}><b style={{ textTransform: 'capitalize' }}>{k}:</b> {detail}</div>;
              })}
            </div>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 20, marginBottom: 20 }}>
        {settlements.map((s) => (
          <div key={s.id} className="panel-card" style={{ margin: 0 }}>
            <div className="panel-header">
              <div>
                <div style={{ fontSize: 15, fontWeight: 800 }}>#{s.priorityRank} {s.name}</div>
                <div style={{ fontSize: 11, color: '#64748b' }}>
                  {s.rainfall} mm · gauge {s.waterLevelMeters} m · {s.relativeElevation} m above river · {s.groundReportsCount} report(s)
                  {s.imputedFields.length > 0 && <span title="Filled by the data processing layer"> · imputed: {s.imputedFields.join(', ')}</span>}
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <span className={`status-badge ${riskBadgeClass(s.riskStatus)}`}>{s.riskStatus} {s.riskScore}</span>
                <div style={{ fontSize: 10, color: '#64748b', marginTop: 3 }}>confidence {pct(s.riskConfidence)}</div>
              </div>
            </div>
            <div className="panel-body">
              <div style={{ fontSize: 11, fontWeight: 700, color: '#475569', textTransform: 'uppercase', marginBottom: 6 }}>Risk factors</div>
              <FactorBars factors={s.riskFactors} color={RISK_COLORS[s.riskStatus]} />
              <div style={{ fontSize: 11, fontWeight: 700, color: '#475569', textTransform: 'uppercase', margin: '12px 0 6px' }}>Priority factors → {s.responsePriority}/100</div>
              <FactorBars factors={s.priorityFactors} color="#2563eb" />
              <ul style={{ margin: '10px 0 0 16px', padding: 0, fontSize: 11, color: '#334155' }}>
                {s.priorityWhy.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
              {s.rankReason && <div style={{ fontSize: 11, color: '#64748b', fontStyle: 'italic', marginTop: 6 }}>{s.rankReason}</div>}
            </div>
          </div>
        ))}
      </div>

      <div className="panel-card">
        <div className="panel-header">
          <div className="panel-title"><History size={16} color="#7c3aed" /><span>Decision history (most recent first)</span></div>
        </div>
        <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {systemState.eventLog.length === 0 && <div style={{ fontSize: 12, color: '#64748b' }}>No events yet — use the demo steps or what-if controls.</div>}
          {systemState.eventLog.map((e) => <ChangeLog key={e.id} entry={e} />)}
        </div>
      </div>
    </div>
  );
}
