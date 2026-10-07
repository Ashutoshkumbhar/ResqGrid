import React, { useEffect, useState } from 'react';
import { BarChart, Bar, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from 'recharts';
import { Activity, Gauge, Users, TimerReset, TriangleAlert } from 'lucide-react';
import { api } from '../utils';

const metricMeta = [
  { key: 'villagesReached', label: 'Villages reached', icon: Users, color: '#38bdf8' },
  { key: 'totalPopulationReached', label: 'Population reached', icon: Users, color: '#22c55e' },
  { key: 'averageResponseTimeMinutes', label: 'Avg response time', icon: TimerReset, color: '#f59e0b' },
  { key: 'wastedDispatches', label: 'Wasted dispatches', icon: TriangleAlert, color: '#ef4444' },
];

function formatMetric(metric, value) {
  if (metric.key === 'averageResponseTimeMinutes') return `${value} min`;
  if (metric.key === 'totalPopulationReached') return `${value.toLocaleString()} people`;
  return value;
}

export default function ImpactPage() {
  const [impact, setImpact] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let live = true;
    api('/api/impact/compare')
      .then((data) => {
        if (live) setImpact(data);
      })
      .catch((err) => {
        if (live) setError(err.message);
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => { live = false; };
  }, []);

  if (loading) {
    return (
      <div style={{ padding: 24, color: '#e2e8f0' }}>Loading impact comparison…</div>
    );
  }

  if (error || !impact) {
    return (
      <div style={{ padding: 24, color: '#fca5a5' }}>Unable to load impact data: {error || 'No scenario returned.'}</div>
    );
  }

  const withResQGrid = impact.withResQGrid;
  const without = impact.withoutResQGrid;
  const chartData = [
    { name: 'Villages', with: withResQGrid.villagesReached, without: without.villagesReached },
    { name: 'Population', with: withResQGrid.totalPopulationReached / 1000, without: without.totalPopulationReached / 1000 },
    { name: 'Avg ETA', with: withResQGrid.averageResponseTimeMinutes, without: without.averageResponseTimeMinutes },
    { name: 'Wasted', with: withResQGrid.wastedDispatches, without: without.wastedDispatches },
  ];

  return (
    <div style={{ padding: 24, display: 'grid', gap: 20 }}>
      <div className="panel-card" style={{ background: 'linear-gradient(135deg, rgba(15,23,42,0.96), rgba(30,41,59,0.9))' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 12, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#93c5fd', fontWeight: 700 }}>Impact summary</div>
            <h1 style={{ margin: '8px 0 0', fontSize: 32, color: '#e2e8f0' }}>With ResQGrid vs Without</h1>
          </div>
          <div style={{ background: 'rgba(14,116,144,0.18)', color: '#bae6fd', border: '1px solid rgba(125,211,252,0.25)', padding: '10px 16px', borderRadius: 12, fontWeight: 700 }}>
            {impact.headline}
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16 }}>
        {[
          { label: 'Villages reached', data: withResQGrid, value: withResQGrid.villagesReached, comparison: `vs ${without.villagesReached}` },
          { label: 'Population reached', data: withResQGrid, value: withResQGrid.totalPopulationReached.toLocaleString(), comparison: `vs ${without.totalPopulationReached.toLocaleString()}` },
          { label: 'Avg response time', data: withResQGrid, value: `${withResQGrid.averageResponseTimeMinutes} min`, comparison: `vs ${without.averageResponseTimeMinutes} min` },
          { label: 'Wasted dispatches', data: withResQGrid, value: withResQGrid.wastedDispatches, comparison: `vs ${without.wastedDispatches}` },
        ].map((card) => (
          <div key={card.label} className="panel-card" style={{ padding: 18 }}>
            <div style={{ color: '#94a3b8', fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{card.label}</div>
            <div style={{ fontSize: 30, fontWeight: 800, margin: '10px 0 4px', color: '#f8fafc' }}>{card.value}</div>
            <div style={{ color: '#7dd3fc', fontSize: 13, fontWeight: 600 }}>{card.comparison}</div>
          </div>
        ))}
      </div>

      <div className="panel-card" style={{ padding: 18 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, color: '#e2e8f0', fontWeight: 700 }}>
          <Gauge size={18} color="#7dd3fc" />
          Impact comparison by metric
        </div>
        <div style={{ width: '100%', height: 320 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 16 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="name" stroke="#cbd5e1" />
              <YAxis stroke="#cbd5e1" />
              <Tooltip
                formatter={(value, name) => {
                  if (name === 'Population') return [`${Number(value).toFixed(1)}k`, name];
                  if (name === 'Avg ETA') return [`${value} min`, name];
                  return [value, name];
                }}
                contentStyle={{ background: '#0f172a', border: '1px solid #334155', color: '#e2e8f0' }}
              />
              <Legend />
              <Bar dataKey="with" name="With ResQGrid" fill="#38bdf8" radius={[6, 6, 0, 0]} />
              <Bar dataKey="without" name="Without" fill="#f97316" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
        <div className="panel-card" style={{ padding: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#a7f3d0', fontWeight: 700 }}><Activity size={18} /> Faster response</div>
          <div style={{ fontSize: 26, fontWeight: 800, marginTop: 12, color: '#f8fafc' }}>{impact.delta.fasterPercent}%</div>
          <div style={{ color: '#94a3b8', marginTop: 4 }}>Reduction in average response time.</div>
        </div>
        <div className="panel-card" style={{ padding: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#c4b5fd', fontWeight: 700 }}><Users size={18} /> More people reached</div>
          <div style={{ fontSize: 26, fontWeight: 800, marginTop: 12, color: '#f8fafc' }}>{impact.delta.morePopulationSaved.toLocaleString()}</div>
          <div style={{ color: '#94a3b8', marginTop: 4 }}>Additional population reached under ResQGrid.</div>
        </div>
      </div>
    </div>
  );
}
