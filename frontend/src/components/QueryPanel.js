import React, { useState } from 'react';

export default function QueryPanel() {
  const [text, setText] = useState('Show me Python developers hired this year');

  const runQuery = () => {
    // Placeholder: wire up to backend later
    alert('Query sent: ' + text);
  };

  return (
    <div style={{ border: '1px solid #ddd', padding: 16, borderRadius: 8 }}>
      <h3>Query Panel</h3>
      <textarea rows={3} style={{ width: '100%' }} value={text} onChange={(e) => setText(e.target.value)} />
      <div style={{ marginTop: 8 }}>
        <button onClick={runQuery}>Run</button>
      </div>
    </div>
  );
}
