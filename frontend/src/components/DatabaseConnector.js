import React, { useState } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api';

export default function DatabaseConnector() {
  const [conn, setConn] = useState('sqlite:///./example.db');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [schema, setSchema] = useState(null);

  const handleConnect = async () => {
    setLoading(true);
    setError('');
    setSchema(null);
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
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ border: '1px solid #ddd', padding: 16, borderRadius: 8 }}>
      <h3>Database Connector</h3>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          style={{ flex: 1 }}
          value={conn}
          onChange={(e) => setConn(e.target.value)}
          placeholder="Enter SQLAlchemy connection string"
        />
        <button onClick={handleConnect} disabled={loading}>
          {loading ? 'Connecting...' : 'Connect'}
        </button>
      </div>
      {error && <p style={{ color: 'red' }}>{error}</p>}
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
