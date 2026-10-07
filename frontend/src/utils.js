export const RISK_COLORS = {
  CRITICAL: '#dc2626',
  HIGH: '#ea580c',
  MODERATE: '#ca8a04',
  LOW: '#16a34a',
};

export const ROAD_COLORS = {
  OPEN: '#10b981',
  AT_RISK: '#f59e0b',
  BLOCKED: '#ef4444',
};

export const RESOURCE_ICONS = {
  RESCUE_BOAT: '🚤',
  AMBULANCE: '🚑',
  RESCUE_TEAM: '🚒',
  HOSPITAL: '🏥',
  SHELTER: '🏠',
};

export const STAGE_COLORS = {
  ROAD: '#ef4444',
  RISK: '#ea580c',
  ACCESS: '#f59e0b',
  PRIORITY: '#2563eb',
  ROUTE: '#7c3aed',
  RESOURCE: '#16a34a',
};

export function riskBadgeClass(status) {
  return { CRITICAL: 'badge-critical', HIGH: 'badge-high', MODERATE: 'badge-moderate', LOW: 'badge-low' }[status] || 'badge-low';
}

export function shortName(name = '') {
  return name.split(' (')[0];
}

// Timestamps come from the backend as ISO strings; seed data may be relative text.
export function fmtTime(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function fmtAgo(ts) {
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts || '';
  const s = Math.max(0, Math.round((Date.now() - d.getTime()) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  return `${fmtTime(ts)}`;
}

export function pct(x) {
  return `${Math.round((x || 0) * 100)}%`;
}

const API_BASE = (import.meta.env?.VITE_API_URL || '').replace(/\/$/, '');

export async function api(path, body, method) {
  const url = API_BASE ? `${API_BASE}${path.startsWith('/') ? path : '/' + path}` : path;
  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData;
  const res = await fetch(url, {
    method: method || (body !== undefined ? 'POST' : 'GET'),
    headers: isFormData ? undefined : body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? (isFormData ? body : JSON.stringify(body)) : undefined,
  });
  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  if (!res.ok) {
    const detail = data?.detail;
    const msg = Array.isArray(detail) ? detail.map((d) => d.msg).join('; ') : detail || `Request failed (${res.status})`;
    throw new Error(msg);
  }
  return data;
}
