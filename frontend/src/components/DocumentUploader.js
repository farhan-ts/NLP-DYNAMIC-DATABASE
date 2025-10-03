import React, { useState } from 'react';

export default function DocumentUploader() {
  const [files, setFiles] = useState([]);

  const handleChange = (e) => setFiles(Array.from(e.target.files || []));

  return (
    <div style={{ border: '1px solid #ddd', padding: 16, borderRadius: 8 }}>
      <h3>Document Uploader</h3>
      <input type="file" multiple onChange={handleChange} />
      <ul>
        {files.map((f) => (
          <li key={f.name}>{f.name}</li>
        ))}
      </ul>
      <button disabled>Upload (placeholder)</button>
    </div>
  );
}
