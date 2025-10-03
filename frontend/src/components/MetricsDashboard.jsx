import React, { useEffect, useMemo, useState } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api';

export default function MetricsDashboard() {
  const [m, setM] = useState(null);
  const [err, setErr] = useState('');

  const refresh = async () => {
    try {
      const res = await fetch(`${API_BASE}/metrics`);
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.detail || 'Failed to load metrics');
      setM(data.metrics);
    } catch (e) {
      setErr(e.message);
    }
  };

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 2000);
    return () => clearInterval(t);
  }, []);

  const hitRatio = useMemo(() => {
    if (!m) return 0;
    const hits = m.cache_hits || 0;
    const total = (m.cache_hits || 0) + (m.cache_misses || 0);
    return total ? (hits / total) : 0;
  }, [m]);

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <h3 style={{ margin: 0 }}>Metrics</h3>
        <div className="toolbar" style={{ margin: 0 }}>
          <button className="btn btn-primary" onClick={async () => { await fetch(`${API_BASE}/metrics/reset`, { method: 'POST' }); refresh(); }}>Reset Metrics</button>
          <button className="btn btn-secondary" onClick={refresh}>Refresh</button>
        </div>
      </div>
      {err && <p style={{ color: 'red' }}>{err}</p>}
      {!m && !err && <p>Loading...</p>}
      {m && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 16 }}>
          <div className="fade-in">
            <h4>Query Performance</h4>
            <div className="muted" style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
              <span>Total queries: {m.total_queries}</span>
              <span>Active queries: {m.active_queries}</span>
              <span>Avg time: {m.avg_exec_sec?.toFixed?.(3)}s</span>
              <span>P95 time: {m.p95_exec_sec?.toFixed?.(3)}s</span>
            </div>
            <div style={{ marginTop: 8 }}>
              <Sparkline data={m.recent_exec_times || []} height={80} />
            </div>
          </div>
          <div className="fade-in">
            <h4>Cache & Index</h4>
            <div className="muted" style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
              <span>Cache hits: {m.cache_hits} / misses: {m.cache_misses}</span>
              <span>Hit ratio: {(hitRatio * 100).toFixed(1)}%</span>
              <span>Indexed docs: {m.indexed_documents}</span>
              <span>Indexed chunks: {m.indexed_chunks}</span>
            </div>
            <div style={{ marginTop: 8 }}>
              <Bar ratio={hitRatio} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Sparkline({ data, width = '100%', height = 30 }) {
  if (!data || data.length === 0) return <div style={{ height }}>No data</div>;
  const max = Math.max(...data, 0.001);
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * 100;
    const y = 100 - (v / max) * 100;
    return `${x},${y}`;
  }).join(' ');
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ width, height, background: '#fafafa', border: '1px solid #eee' }}>
      <polyline fill="none" stroke="#4f46e5" strokeWidth="2" points={points} />
    </svg>
  );
}

function Bar({ ratio }) {
  const pct = Math.max(0, Math.min(1, ratio)) * 100;
  return (
    <div style={{ height: 12, background: '#eee', borderRadius: 6, overflow: 'hidden' }}>
      <div style={{ height: '100%', width: `${pct}%`, background: '#16a34a' }} />
    </div>
  );
}
