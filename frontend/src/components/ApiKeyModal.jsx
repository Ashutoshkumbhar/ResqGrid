import React, { useState, useEffect } from 'react';
import { 
  KeyRound, 
  CheckCircle, 
  X, 
  Save, 
  Cpu, 
  CloudRain, 
  Navigation, 
  Wifi,
  Sparkles,
  ExternalLink
} from 'lucide-react';

export default function ApiKeyModal({ isOpen, onClose, onSaveGeminiKey }) {
  const [geminiKey, setGeminiKey] = useState('');
  const [configStatus, setConfigStatus] = useState(null);
  const [saving, setSaving] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null);

  useEffect(() => {
    if (isOpen) {
      fetch('/api/config/status')
        .then(res => res.json())
        .then(data => setConfigStatus(data))
        .catch(err => console.error(err));
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSave = async (e) => {
    e.preventDefault();
    if (!geminiKey.trim()) return;

    setSaving(true);
    try {
      await onSaveGeminiKey(geminiKey.trim());
      setStatusMsg('✓ Gemini API Key saved & active!');
      setGeminiKey('');
      // Refresh config status
      const res = await fetch('/api/config/status');
      const data = await res.json();
      setConfigStatus(data);
    } catch (err) {
      setStatusMsg('Failed to save key');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'rgba(15, 23, 42, 0.75)',
      backdropFilter: 'blur(4px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 9999,
      padding: '16px'
    }}>
      <div style={{
        background: '#ffffff',
        borderRadius: '12px',
        maxWidth: '540px',
        width: '100%',
        boxShadow: '0 20px 40px rgba(0,0,0,0.3)',
        overflow: 'hidden',
        border: '1px solid #cbd5e1'
      }}>
        {/* Modal Header */}
        <div style={{
          padding: '16px 20px',
          background: '#0f172a',
          color: '#ffffff',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <KeyRound size={18} style={{ color: '#38bdf8' }} />
            <span style={{ fontWeight: 800, fontSize: '15px' }}>API Configurations & Live Pipelines</span>
          </div>
          <button 
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ padding: '20px' }}>
          
          {/* Active Data Pipelines Overview */}
          <div style={{ marginBottom: '20px' }}>
            <div style={{ fontSize: '11px', fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>
              Active Real-Time Telemetry Providers:
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 10px', background: '#f8fafc', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#334155' }}>
                  <Wifi size={13} style={{ color: '#10b981' }} />
                  <b>Live Push Stream</b>
                </span>
                <span style={{ color: '#10b981', fontWeight: 700 }}>WebSocket (/ws/live) Connected</span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 10px', background: '#f8fafc', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#334155' }}>
                  <CloudRain size={13} style={{ color: '#0284c7' }} />
                  <b>Rainfall & Weather</b>
                </span>
                <span style={{ color: '#0284c7', fontWeight: 700 }}>Open-Meteo API (Scheduled Poller)</span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 10px', background: '#f8fafc', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#334155' }}>
                  <Navigation size={13} style={{ color: '#f59e0b' }} />
                  <b>Dynamic Routing</b>
                </span>
                <span style={{ color: '#b45309', fontWeight: 700 }}>NetworkX + OSRM Local Graph</span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 10px', background: '#f8fafc', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#334155' }}>
                  <Sparkles size={13} style={{ color: '#7c3aed' }} />
                  <b>AI Entity Extraction</b>
                </span>
                <span style={{ color: configStatus?.geminiConfigured ? '#15803d' : '#475569', fontWeight: 700 }}>
                  {configStatus?.aiProvider || 'Deterministic NLP Fallback'}
                </span>
              </div>
            </div>
          </div>

          {/* Gemini API Key Form */}
          <form onSubmit={handleSave}>
            <div style={{ marginBottom: '12px' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#0f172a', marginBottom: '4px' }}>
                Google Gemini API Key (Optional):
              </label>
              <p style={{ fontSize: '11px', color: '#64748b', marginBottom: '6px' }}>
                Provide your Gemini key for live LLM ground report parsing. If left blank, ResQGrid seamlessly operates using the local deterministic NLP parsing engine!
              </p>
              <input
                type="password"
                value={geminiKey}
                onChange={(e) => setGeminiKey(e.target.value)}
                placeholder="AIzaSy..."
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  borderRadius: '6px',
                  border: '1px solid #cbd5e1',
                  fontSize: '13px',
                  fontFamily: 'monospace'
                }}
              />
            </div>

            {statusMsg && (
              <div style={{ fontSize: '12px', color: '#16a34a', fontWeight: 600, marginBottom: '10px' }}>
                {statusMsg}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button
                type="button"
                onClick={onClose}
                className="btn btn-secondary"
                style={{ padding: '7px 12px' }}
              >
                Close
              </button>
              <button
                type="submit"
                disabled={saving || !geminiKey.trim()}
                className="btn btn-primary"
                style={{ padding: '7px 14px' }}
              >
                <Save size={13} />
                <span>{saving ? 'Saving...' : 'Apply Key'}</span>
              </button>
            </div>
          </form>

        </div>
      </div>
    </div>
  );
}
