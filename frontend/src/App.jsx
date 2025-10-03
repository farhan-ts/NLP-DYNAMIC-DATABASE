import React, { useEffect, useState } from 'react';
import DatabaseConnector from './components/DatabaseConnector.jsx';
import DocumentUploader from './components/DocumentUploader.jsx';
import QueryPanel from './components/QueryPanel.jsx';
import ResultsView from './components/ResultsView.jsx';
import MetricsDashboard from './components/MetricsDashboard.jsx';

export default function App() {
  const [queryResult, setQueryResult] = useState(null);
  const [queryLoading, setQueryLoading] = useState(false);
  const [queryError, setQueryError] = useState('');
  const [theme, setTheme] = useState('light');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme === 'dark' ? 'dark' : 'light');
  }, [theme]);

  return (
    <div className="container">
      <div className="header">
        <div>
          <h1 className="app-title gradient-text">NLP Query Engine</h1>
          <div className="subtitle">for Employee Data</div>
          <div className="badges" style={{ marginTop: 8 }}>
            <a className="badge" href="https://fastapi.tiangolo.com/" target="_blank" rel="noopener noreferrer">FastAPI</a>
            <a className="badge" href="https://react.dev/" target="_blank" rel="noopener noreferrer">React</a>
            <a className="badge" href="https://docs.sqlalchemy.org/" target="_blank" rel="noopener noreferrer">SQL</a>
            <a className="badge" href="https://python.langchain.com/docs/modules/data_connection/document_loaders/" target="_blank" rel="noopener noreferrer">Document</a>
            <a className="badge" href="https://www.elastic.co/guide/en/elasticsearch/reference/current/semantic-search.html" target="_blank" rel="noopener noreferrer">Hybrid Search</a>
          </div>
        </div>
        <div className="toggle">
          <div
            role="button"
            aria-label="Toggle dark mode"
            className={`toggle-pill ${theme === 'dark' ? 'on' : ''}`}
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          >
            <div className="thumb" />
          </div>
          <span className="muted" style={{ fontSize: 12 }}>{theme === 'dark' ? 'Dark mode: On' : 'Dark mode: Off'}</span>
        </div>
      </div>

      <section className="section fade-in">
        <h3>Connect Database</h3>
        <div className="card">
          <DatabaseConnector />
        </div>
      </section>

      <section className="section fade-in">
        <h3>Upload Documents</h3>
        <div className="card">
          <DocumentUploader />
        </div>
      </section>

      <section className="section fade-in">
        <h3>Query Interface</h3>
        <div className="card">
          <QueryPanel
            setQueryResult={setQueryResult}
            setQueryLoading={setQueryLoading}
            setQueryError={setQueryError}
          />
        </div>
      </section>

      <section className="section fade-in">
        <h3>Result Display</h3>
        <div className="card">
          <ResultsView result={queryResult} loading={queryLoading} error={queryError} />
        </div>
      </section>

      <section className="section fade-in">
        <h3>Metrics Dashboard</h3>
        <div className="card">
          <MetricsDashboard />
        </div>
      </section>
    </div>
  );
}
