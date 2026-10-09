import React, { useEffect, useMemo, useState } from 'react';
import { Camera, CheckCircle, Loader2, LocateFixed, Send, ShieldAlert } from 'lucide-react';
import { api, pct } from '../utils';

const field = { width: '100%', padding: '11px 12px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: 15, background: '#fff' };
const label = { display: 'block', fontSize: 12, fontWeight: 800, color: '#334155', marginBottom: 6, textTransform: 'uppercase' };

export default function MobileReportPage() {
  const [file, setFile] = useState(null);
  const [text, setText] = useState('');
  const [coords, setCoords] = useState(null);
  const [locating, setLocating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const preview = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);

  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview);
  }, [preview]);

  const locate = () => {
    setError(null);
    if (!navigator.geolocation) {
      setError('Location is not available on this device.');
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCoords({ latitude: pos.coords.latitude, longitude: pos.coords.longitude });
        setLocating(false);
      },
      (err) => {
        setError(err.message || 'Location permission was denied.');
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!file) {
      setError('Add a flood photo first.');
      return;
    }
    setSubmitting(true);
    setError(null);
    const formData = new FormData();
    formData.append('image', file);
    formData.append('text', text.trim());
    if (coords) {
      formData.append('latitude', String(coords.latitude));
      formData.append('longitude', String(coords.longitude));
    }
    try {
      const payload = await api('/api/reports/photo', formData, 'POST');
      setResult(payload);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mobile-report-page">
      <header className="mobile-report-header">
        <div className="mobile-report-brand"><ShieldAlert size={18} /> ResQGrid</div>
        <div className="mobile-report-title">Citizen flood report</div>
      </header>

      <main className="mobile-report-main">
        {result ? (
          <section className="mobile-result">
            <CheckCircle size={38} color="#16a34a" />
            <h1>Report received</h1>
            <p>{result.report?.location || 'Nearest settlement'} has been recalculated on the command dashboard.</p>
            <div className="mobile-result-grid">
              <div><span>Severity</span><b>{result.report?.severity}</b></div>
              <div><span>AI source</span><b>{result.parsed?.source || 'LOCAL'}</b></div>
              <div><span>Confidence</span><b>{pct(result.parsed?.confidence || result.report?.extractedInfo?.confidence || 0)}</b></div>
              <div><span>Road passable</span><b>{String(result.parsed?.roadPassable ?? 'review')}</b></div>
            </div>
            {result.report?.downstreamChanges?.length > 0 && (
              <div className="mobile-changes">
                {result.report.downstreamChanges.slice(0, 4).map((change, index) => (
                  <div key={index}><b>{change.stage}</b> {change.text}</div>
                ))}
              </div>
            )}
            <button className="btn btn-primary" type="button" onClick={() => { setResult(null); setFile(null); setText(''); }}>
              Send another report
            </button>
          </section>
        ) : (
          <form className="mobile-report-card" onSubmit={submit}>
            <div>
              <label style={label}>Flood photo</label>
              <label className="mobile-photo-picker">
                {preview ? <img src={preview} alt="Flood preview" /> : <Camera size={34} />}
                <input type="file" accept="image/*" capture="environment" onChange={(e) => setFile(e.target.files?.[0] || null)} />
              </label>
            </div>

            <div>
              <label style={label}>Optional note</label>
              <textarea
                rows={4}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Road blocked, water level, trapped people..."
                style={{ ...field, fontFamily: 'inherit', resize: 'vertical' }}
              />
            </div>

            <button className="btn btn-secondary" type="button" onClick={locate} disabled={locating}>
              {locating ? <Loader2 size={16} className="spin" /> : <LocateFixed size={16} />}
              {coords ? `Location added (${coords.latitude.toFixed(4)}, ${coords.longitude.toFixed(4)})` : 'Use my location'}
            </button>

            {error && <div className="mobile-error">{error}</div>}

            <button className="btn btn-primary mobile-submit" type="submit" disabled={submitting}>
              {submitting ? <Loader2 size={16} className="spin" /> : <Send size={16} />}
              {submitting ? 'Analyzing photo...' : 'Send live report'}
            </button>
          </form>
        )}
      </main>
    </div>
  );
}
