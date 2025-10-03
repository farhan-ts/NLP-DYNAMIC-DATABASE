import React, { useEffect, useState } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api';

export default function QueryPanel({ setQueryResult, setQueryLoading, setQueryError }) {
  const [text, setText] = useState('Show me Python developers hired this year');
  const [suggestions, setSuggestions] = useState([]);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    // Load recent history for simple autocomplete suggestions
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/query/history`);
        const data = await res.json();
        if (res.ok && data.ok) setSuggestions((data.history || []).map(h => h.q).slice(0, 5));
      } catch {}
    })();
  }, []);

  const runQuery = async () => {
    setQueryLoading(true);
    setRunning(true);
    setQueryError('');
    setQueryResult(null);
    try {
      const res = await fetch(`${API_BASE}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: text }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.detail || 'Query failed');
      // Backend may return HTTP 200 with an error field; surface to user
      if (data.error) {
        setQueryError(data.error);
        return;
      }
      setQueryResult(data);
    } catch (e) {
      setQueryError(e.message);
    } finally {
      setQueryLoading(false);
      setRunning(false);
    }
  };

  const applySuggestion = (s) => setText(s);

  return (
    <div>
      <textarea
        rows={3}
        className="input"
        style={{ width: '100%' }}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Type your query (e.g., 'Python developers hired in 2024')"
      />

      {suggestions.length > 0 && (
        <div className="chips">
          {suggestions.map((s, i) => (
            <button key={i} onClick={() => applySuggestion(s)} className="chip">
              {s}
            </button>
          ))}
        </div>
      )}

      <div className="toolbar">
        <button className="btn btn-success" onClick={runQuery} disabled={running || !text.trim()}>
          {running ? (<span><span className="spinner" style={{ marginRight: 8 }} />Running...</span>) : 'Run'}
        </button>
      </div>
    </div>
  );
}
