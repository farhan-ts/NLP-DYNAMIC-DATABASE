import React, { useRef, useState } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api';

export default function DocumentUploader() {
  const [files, setFiles] = useState([]);
  const [dragging, setDragging] = useState(false);
  const [jobId, setJobId] = useState('');
  const [status, setStatus] = useState(null);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef();

  const handleChange = (e) => setFiles(Array.from(e.target.files || []));

  const onDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(false);
    const dropped = Array.from(e.dataTransfer.files || []);
    if (dropped.length) setFiles((prev) => [...prev, ...dropped]);
  };

  const onDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(true);
  };

  const onDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(false);
  };

  const upload = async () => {
    if (!files.length) return;
    setUploading(true);
    setStatus(null);
    setJobId('');
    try {
      const form = new FormData();
      for (const f of files) form.append('files', f);
      const res = await fetch(`${API_BASE}/upload-documents`, {
        method: 'POST',
        body: form,
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.detail || 'Upload failed');
      setJobId(data.job_id);
      pollStatus(data.job_id);
    } catch (e) {
      setStatus({ error: e.message });
    } finally {
      setUploading(false);
    }
  };

  const pollStatus = async (id) => {
    let done = false;
    while (!done) {
      try {
        const res = await fetch(`${API_BASE}/ingestion-status/${id}`);
        const data = await res.json();
        setStatus(data);
        if (data.status === 'completed' || data.status === 'failed' || data.status === 'not_found') {
          done = true;
        } else {
          await new Promise((r) => setTimeout(r, 1000));
        }
      } catch (e) {
        setStatus({ error: e.message });
        done = true;
      }
    }
  };

  const statusText = status?.status || (status?.error ? 'failed' : null);
  const isSuccess = statusText === 'completed';
  const isFailed = statusText === 'failed' || status?.status === 'failed';
  const total = typeof status?.total_files === 'number' ? status.total_files : null;
  const done = typeof status?.processed_files === 'number' ? status.processed_files : null;
  const pct = total && done != null && total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0;

  return (
    <div>
      <div
        className={`dropzone ${dragging ? 'dragging' : ''}`}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onClick={() => inputRef.current?.click()}
      >
        Drag & drop PDF/DOCX/TXT/CSV here or click to select
        <input ref={inputRef} type="file" multiple onChange={handleChange} style={{ display: 'none' }} />
      </div>

      {files.length > 0 && (
        <ul className="fade-in" style={{ marginTop: 10 }}>
          {files.map((f) => (
            <li key={f.name}>{f.name}</li>
          ))}
        </ul>
      )}

      <div className="toolbar">
        <button className="btn btn-primary" onClick={upload} disabled={uploading || files.length === 0}>
          {uploading ? (<span><span className="spinner" style={{ marginRight: 8 }} />Uploading...</span>) : 'Upload & Ingest'}
        </button>
        <button className="btn btn-secondary" onClick={() => { setFiles([]); setStatus(null); setJobId(''); }}>
          Clear
        </button>
      </div>

      {jobId && <p className="muted" style={{ marginTop: 8 }}>Job ID: <code>{jobId}</code></p>}
      {status && (
        <div className="fade-in" style={{ marginTop: 8 }}>
          <div>
            <strong>Status: </strong>
            {isSuccess && <span className="text-success">completed</span>}
            {isFailed && <span className="text-error">failed</span>}
            {!isSuccess && !isFailed && <span className="muted">{status.status || 'pending'}</span>}
          </div>
          {total != null && done != null && (
            <div style={{ marginTop: 8 }}>
              <div className="progress"><div className="progress-bar" style={{ width: `${pct}%` }} /></div>
              <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>Progress: {done} / {total} ({pct}%)</div>
            </div>
          )}
          {status.error && <div className="text-error" style={{ marginTop: 8 }}>Error: {status.error}</div>}
        </div>
      )}
    </div>
  );
}
