import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { RISK_COLORS, ROAD_COLORS, RESOURCE_ICONS, shortName } from '../utils';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function settlementPopup(s) {
  const color = RISK_COLORS[s.riskStatus];
  const row = (k, v) => `<div style="display:flex;justify-content:space-between;gap:12px;margin-bottom:3px"><span>${k}</span><b>${v}</b></div>`;
  return `
    <div style="font-family:Inter,sans-serif;font-size:12px;min-width:240px;line-height:1.4">
      <div style="font-size:14px;font-weight:800;border-bottom:1px solid #e2e8f0;padding-bottom:4px;margin-bottom:6px">${esc(s.name)}</div>
      ${row('Population', s.population.toLocaleString())}
      ${row('Rainfall (24h)', `${s.rainfall} mm · ${s.rainfallIntensity} mm/h`)}
      ${row('Elevation', `${s.elevation} m ASL (${s.relativeElevation} m above river)`)}
      ${row('Water level', `${s.waterLevelMeters} m (${s.waterLevel})`)}
      ${row('Risk score', `<span style="color:${color}">${s.riskScore}/100 ${s.riskStatus}</span>`)}
      ${row('Priority', `#${s.priorityRank} (${s.responsePriority})`)}
      ${row('Road access', `<span style="color:${s.accessibility === 'OPEN' ? '#16a34a' : s.accessibility === 'CUT_OFF' ? '#dc2626' : '#d97706'}">${s.accessibility.replace('_', ' ')}</span>`)}
      ${row('Confidence', `${Math.round(s.riskConfidence * 100)}%`)}
      <div style="background:#f8fafc;padding:6px;border-radius:4px;border:1px solid #e2e8f0;margin-top:4px">
        <b>Evidence</b>
        <ul style="margin:4px 0 0 14px;padding:0">${(s.evidence || []).map((e) => `<li>${esc(e)}</li>`).join('') || '<li>No strong flood signals</li>'}</ul>
      </div>
    </div>`;
}

export default function MapView({ systemState, onSelectSettlement = null, height = '520px', focusSettlementId = null, forecastHour = 0 }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const [tilesOffline, setTilesOffline] = useState(false);
  const forecastBySettlement = systemState?.forecast?.settlements || {};

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return undefined;
    const map = L.map(containerRef.current, { center: [18.578, 73.792], zoom: 13 });
    let errors = 0;
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 18,
    })
      .on('tileerror', () => { errors += 1; if (errors > 3) setTilesOffline(true); })
      .on('tileload', () => { errors = 0; setTilesOffline(false); })
      .addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer || !systemState) return;
    layer.clearLayers();
    const { settlements = [], roads = [], resources = [], routes = [], nodes: bases = [] } = systemState;
    const boundary = systemState.district?.boundary;

    // District boundary (local geometry — renders even without tiles)
    if (boundary) {
      layer.addLayer(L.polygon(boundary, { color: '#334155', weight: 1.5, dashArray: '4 4', fill: false, interactive: false }));
    }

    // Risk areas
    settlements.forEach((s) => {
      const forecast = forecastBySettlement[s.id]?.riskByHour?.find((point) => point.hour === forecastHour) || forecastBySettlement[s.id]?.riskByHour?.[0];
      const status = forecast?.riskStatus || s.riskStatus;
      const score = forecast?.riskScore ?? s.riskScore;
      const color = RISK_COLORS[status];
      layer.addLayer(L.circle([s.latitude, s.longitude], {
        radius: 350 + score * 10, color, fillColor: color, weight: 1,
        fillOpacity: status === 'CRITICAL' ? 0.25 : status === 'HIGH' ? 0.18 : 0.1, interactive: false,
      }));
    });

    // Roads
    roads.forEach((road) => {
      const color = ROAD_COLORS[road.status];
      const line = L.polyline(road.coordinates, {
        color, weight: road.status === 'OPEN' ? 4 : 5, opacity: 0.85, dashArray: road.status === 'BLOCKED' ? '6 6' : null,
      });
      line.bindPopup(`<div style="font-size:12px"><b>${esc(road.name)} (${road.id})</b><br/>${esc(road.sourceName)} ↔ ${esc(road.destinationName)}<br/>
        Status: <b style="color:${color}">${road.status.replace('_', ' ')}</b> · ${road.distanceKm} km<br/><i>${esc(road.statusReason)}</i></div>`);
      layer.addLayer(line);
      const mid = road.coordinates[Math.floor(road.coordinates.length / 2)];
      layer.addLayer(L.marker(mid, {
        interactive: false,
        icon: L.divIcon({
          className: '',
          html: `<div style="background:${road.status === 'BLOCKED' ? '#dc2626' : '#0f172a'};color:#fff;font-size:9px;font-weight:800;padding:1px 4px;border-radius:3px;border:1px solid ${color};white-space:nowrap">${road.status === 'BLOCKED' ? '✕ ' : ''}${road.id}</div>`,
          iconSize: [30, 14], iconAnchor: [15, 7],
        }),
      }));
    });

    // Response routes (original, and alternative when rerouted)
    routes.forEach((route) => {
      if (route.originalCoordinates?.length > 1) {
        const invalid = route.originalRouteStatus === 'INVALID';
        const line = L.polyline(route.originalCoordinates, {
          color: invalid ? '#991b1b' : '#2563eb', weight: invalid ? 3 : 7, opacity: invalid ? 0.9 : 0.55, dashArray: invalid ? '2 8' : null,
        });
        line.bindPopup(`<div style="font-size:12px"><b>${esc(route.resourceName)} → ${esc(shortName(route.targetSettlementName))}</b><br/>
          Original route: <b style="color:${invalid ? '#dc2626' : '#16a34a'}">${route.originalRouteStatus}</b> (${route.originalRoadIds.join(' → ')})<br/>${esc(route.explanation)}</div>`);
        layer.addLayer(line);
      }
      if (route.alternativeCoordinates?.length > 1) {
        const alt = L.polyline(route.alternativeCoordinates, { color: '#2563eb', weight: 7, opacity: 0.6 });
        alt.bindPopup(`<div style="font-size:12px"><b style="color:#2563eb">✓ Alternative route VALID</b><br/>${esc(route.resourceName)} → ${esc(shortName(route.targetSettlementName))}<br/>
          ${route.alternativeRoadIds.join(' → ')} · ${route.distanceKm} km · ETA ${route.etaMinutes} min</div>`);
        layer.addLayer(alt);
      }
    });

    // Bases
    bases.forEach((b) => {
      layer.addLayer(L.circleMarker([b.latitude, b.longitude], { radius: 5, color: '#0f172a', fillColor: '#38bdf8', fillOpacity: 1, weight: 2 })
        .bindTooltip(b.name));
    });

    // Settlements
    settlements.forEach((s) => {
      const forecast = forecastBySettlement[s.id]?.riskByHour?.find((point) => point.hour === forecastHour) || forecastBySettlement[s.id]?.riskByHour?.[0];
      const status = forecast?.riskStatus || s.riskStatus;
      const score = forecast?.riskScore ?? s.riskScore;
      const color = RISK_COLORS[status];
      const focused = s.id === focusSettlementId;
      const marker = L.marker([s.latitude, s.longitude], {
        zIndexOffset: 1000,
        icon: L.divIcon({
          className: '',
          html: `<div style="position:relative">
            <div style="background:${color};color:#fff;border:${focused ? 3 : 2}px solid ${focused ? '#0f172a' : '#fff'};border-radius:50%;width:32px;height:32px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:800;box-shadow:0 4px 8px rgba(0,0,0,.3)">#${s.priorityRank}</div>
            <div style="background:rgba(15,23,42,.88);color:#fff;font-size:10px;font-weight:700;padding:2px 6px;border-radius:4px;position:absolute;top:34px;left:50%;transform:translateX(-50%);white-space:nowrap">${esc(shortName(s.name))} · ${score}</div>
          </div>`,
          iconSize: [32, 32], iconAnchor: [16, 16],
        }),
      });
      marker.bindPopup(settlementPopup(s), { maxWidth: 320 });
      marker.on('click', () => onSelectSettlement && onSelectSettlement(s.id));
      layer.addLayer(marker);
    });

    // Resources
    resources.forEach((res) => {
      const statusColor = { AVAILABLE: '#16a34a', DEPLOYED: '#2563eb', BUSY: '#d97706', UNAVAILABLE: '#64748b' }[res.status];
      const m = L.marker([res.latitude, res.longitude], {
        icon: L.divIcon({
          className: '',
          html: `<div style="background:#1e293b;border:2px solid ${statusColor};border-radius:8px;width:30px;height:30px;display:flex;align-items:center;justify-content:center;font-size:15px;box-shadow:0 2px 6px rgba(0,0,0,.4)">${RESOURCE_ICONS[res.type] || '📍'}</div>`,
          iconSize: [30, 30], iconAnchor: [15, 15],
        }),
      });
      m.bindPopup(`<div style="font-size:12px"><b>${esc(res.name)}</b><br/>${res.type.replace('_', ' ')} · ${esc(res.locationName)}<br/>Status: <b style="color:${statusColor}">${res.status}</b></div>`);
      layer.addLayer(m);
    });
  }, [systemState, focusSettlementId, onSelectSettlement, forecastHour, forecastBySettlement]);

  const legend = [
    ['dot', RISK_COLORS.CRITICAL, 'Critical'], ['dot', RISK_COLORS.HIGH, 'High'], ['dot', RISK_COLORS.MODERATE, 'Moderate'], ['dot', RISK_COLORS.LOW, 'Low'],
    ['line', ROAD_COLORS.OPEN, 'Road open'], ['line', ROAD_COLORS.AT_RISK, 'Road at risk'], ['line', ROAD_COLORS.BLOCKED, 'Road blocked'],
    ['route', '#2563eb', 'Active route'], ['dash', '#991b1b', 'Invalid route'],
  ];

  return (
    <div style={{ position: 'relative', width: '100%', height }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%', background: '#e2e8f0' }} />
      {tilesOffline && (
        <div style={{ position: 'absolute', top: 12, right: 12, zIndex: 500, background: '#fef3c7', color: '#92400e', border: '1px solid #f59e0b', padding: '6px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600 }}>
          Map tiles offline — showing local district geometry only
        </div>
      )}
      <div style={{
        position: 'absolute', bottom: 16, left: 16, zIndex: 500, background: 'rgba(15,23,42,0.92)', color: '#fff',
        padding: '10px 12px', borderRadius: 8, fontSize: 11, border: '1px solid rgba(255,255,255,0.15)',
      }}>
        <div style={{ fontWeight: 700, marginBottom: 6, textTransform: 'uppercase', color: '#94a3b8', letterSpacing: '0.5px' }}>Map legend</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, auto)', gap: '4px 14px' }}>
          {legend.map(([kind, color, label]) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              {kind === 'dot' && <span style={{ width: 10, height: 10, borderRadius: '50%', background: color }} />}
              {kind === 'line' && <span style={{ width: 14, height: 3, background: color }} />}
              {kind === 'route' && <span style={{ width: 14, height: 5, background: color, opacity: 0.7 }} />}
              {kind === 'dash' && <span style={{ width: 14, height: 0, borderTop: `3px dotted ${color}` }} />}
              <span>{label}</span>
            </div>
          ))}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span>🚤🚑🚒</span><span>Resources</span></div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span>🏥🏠</span><span>Hospital / shelter</span></div>
        </div>
      </div>
    </div>
  );
}
