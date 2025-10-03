import React from 'react';

export default function ResultsView({ result, loading, error }) {
  return (
    <div>
      <h3>Results</h3>
      {loading && <p>Running query...</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {result?.error && <p style={{ color: 'red' }}>{String(result.error)}</p>}
      {result?.warning && <p style={{ color: '#b36b00' }}>{String(result.warning)}</p>}
      {!result && !loading && !error && <p>No results yet. Run a query.</p>}
      {result && <Metrics metrics={result.metrics} />}
      {result && <ExportBar result={result} />}
      {result && renderResult(result)}
    </div>
  );
}

function Metrics({ metrics }) {
  if (!metrics) return null;
  return (
    <div style={{ fontSize: 12, color: '#555' }}>
      <div>Time: {metrics.elapsed_sec?.toFixed?.(3)}s</div>
      <div>Cache: {metrics.cache}</div>
    </div>
  );
}

function renderResult(result) {
  if (result.type === 'sql') return <SQLTable rows={result.rows || []} />;
  if (result.type === 'document') return <DocCards items={result.results || []} />;
  if (result.type === 'hybrid') {
    return (
      <div className="fade-in">
        <div style={{ marginBottom: 16 }}>
          <h4>SQL</h4>
          <SQLTable rows={(result.sql && result.sql.rows) || []} />
        </div>
        <div>
          <h4>Documents</h4>
          <DocCards items={(result.documents && result.documents.results) || []} />
        </div>
      </div>
    );
  }
  return null;
}

function ExportBar({ result }) {
  const download = (filename, content, type) => {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const toCSV = (rows) => {
    if (!rows || rows.length === 0) return '';
    const cols = Object.keys(rows[0]);
    const header = cols.join(',');
    const lines = rows.map(r => cols.map(c => JSON.stringify(String(r[c] ?? '')).replace(/^"|"$/g, '')).join(','));
    return [header, ...lines].join('\n');
  };

  const handleExport = (fmt) => {
    if (result.type === 'sql') {
      const rows = result.rows || [];
      if (fmt === 'csv') download('sql_results.csv', toCSV(rows), 'text/csv');
      else download('sql_results.json', JSON.stringify(rows, null, 2), 'application/json');
    } else if (result.type === 'document') {
      const items = result.results || [];
      if (fmt === 'csv') download('doc_results.csv', toCSV(items), 'text/csv');
      else download('doc_results.json', JSON.stringify(items, null, 2), 'application/json');
    } else if (result.type === 'hybrid') {
      const rows = (result.sql && result.sql.rows) || [];
      const items = (result.documents && result.documents.results) || [];
      if (fmt === 'csv') {
        download('sql_results.csv', toCSV(rows), 'text/csv');
        download('doc_results.csv', toCSV(items), 'text/csv');
      } else {
        download('hybrid_results.json', JSON.stringify({ sql: rows, documents: items }, null, 2), 'application/json');
      }
    }
  };

  return (
    <div className="toolbar">
      <button className="btn btn-primary" onClick={() => handleExport('csv')}>Export CSV</button>
      <button className="btn btn-primary" onClick={() => handleExport('json')}>Export JSON</button>
    </div>
  );
}

function SQLTable({ rows }) {
  if (!rows || rows.length === 0) return <p>No rows.</p>;
  const cols = Object.keys(rows[0] || {});
  return (
    <div style={{ overflow: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {cols.map((c) => (
              <th key={c} style={{ textAlign: 'left', borderBottom: '1px solid #ddd', padding: 4 }}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {cols.map((c) => (
                <td key={c} style={{ borderBottom: '1px solid #f0f0f0', padding: 4 }}>{String(r[c] ?? '')}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DocCards({ items }) {
  if (!items || items.length === 0) return <p>No matches.</p>;
  const top = items.slice(0, 1); // show only the topmost match
  return (
    <div style={{ display: 'grid', gap: 8 }}>
      {top.map((it, idx) => (
        <div key={idx} style={{ padding: 8, borderRadius: 6 }}>
          <div style={{ fontSize: 12, color: '#666' }}>
            {it.filename} ({it.doc_type}) • score: {it.score?.toFixed?.(3)}
          </div>
          <div style={{ whiteSpace: 'pre-wrap' }}>{it.text}</div>
        </div>
      ))}
    </div>
  );
}
