import React, { useState } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api';

export default function DatabaseConnector() {
  const [conn, setConn] = useState('sqlite:///./example.db');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [schema, setSchema] = useState(null);
  const [status, setStatus] = useState('idle'); // idle | success | failed

  const handleConnect = async () => {
    setLoading(true);
    setError('');
    setSchema(null);
    setStatus('idle');
    try {
      const res = await fetch(`${API_BASE}/connect-database`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ connection_string: conn }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        throw new Error(data.detail || 'Failed to connect');
      }
      setSchema(data.schema);
      setStatus('success');
    } catch (e) {
      setError(e.message);
      setStatus('failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="toolbar">
        <input
          className="input"
          style={{ flex: 1 }}
          value={conn}
          onChange={(e) => setConn(e.target.value)}
          placeholder="Enter SQLAlchemy connection string"
        />
        <button className="btn btn-primary" onClick={handleConnect} disabled={loading}>
          {loading ? (<span><span className="spinner" style={{ marginRight: 8 }} />Connecting...</span>) : 'Connect'}
        </button>
      </div>

      {status === 'success' && <div className="text-success">Success</div>}
      {status === 'failed' && <div className="text-error">Failed</div>}
      {error && <p className="text-error" style={{ marginTop: 8 }}>{error}</p>}
      {schema && <SchemaTree schema={schema} />}
    </div>
  );
}

function SchemaTree({ schema }) {
  const { tables = [], columns = {}, relationships = [] } = schema || {};

  return (
    <div style={{ marginTop: 16 }}>
      <h4>Tables</h4>
      <ul>
        {tables.map((t) => (
          <li key={t}>
            <strong>{t}</strong>
            <ul>
              {(columns[t] || []).map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </li>
        ))}
      </ul>

      <h4>Relationships</h4>
      <ul>
        {relationships.length === 0 && <li>None detected</li>}
        {relationships.map((r, idx) => (
          <li key={idx}>
            {r.from_table} ({(r.from_columns || []).join(', ')}) → {r.to_table} ({(r.to_columns || []).join(', ')})
            {r.name ? ` [${r.name}]` : ''}
          </li>
        ))}
      </ul>
    </div>
  );
}
