import React from 'react';
import DatabaseConnector from './components/DatabaseConnector';
import DocumentUploader from './components/DocumentUploader';
import QueryPanel from './components/QueryPanel';
import ResultsView from './components/ResultsView';

export default function App() {
  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', padding: 24, fontFamily: 'Inter, system-ui, sans-serif' }}>
      <h2>NLP Query Engine for Employee Data</h2>
      <p>Backend: FastAPI. Frontend: React (Vite). This is a scaffold with placeholders.</p>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <DatabaseConnector />
        <DocumentUploader />
      </div>
      <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <QueryPanel />
        <ResultsView />
      </div>
    </div>
  );
}
