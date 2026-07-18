import React, { useState, useRef } from 'react';

export default function VideoUploadPanel() {
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setFile(e.dataTransfer.files[0]);
      setUploadStatus('idle');
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setUploadStatus('idle');
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploadStatus('uploading');
    setErrorMessage('');

    const formData = new FormData();
    formData.append('video', file);

    try {
      const response = await fetch('/api/v1/videos/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Upload failed');
      }

      setUploadStatus('success');
      setFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (error: any) {
      console.error('Upload error:', error);
      setUploadStatus('error');
      setErrorMessage(error.message || 'Error uploading video');
    }
  };

  return (
    <section className="panel" style={{ gridArea: 'upload', display: 'flex', flexDirection: 'column' }}>
      <div className="panel-header">
        <h2 className="panel-title">Upload Video</h2>
      </div>

      <div 
        style={{
          flexGrow: 1,
          border: `2px dashed ${isDragging ? 'var(--color-focus)' : 'var(--color-border)'}`,
          borderRadius: 'var(--radius-md)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 'var(--space-4)',
          backgroundColor: isDragging ? 'rgba(96, 165, 250, 0.1)' : 'transparent',
          cursor: 'pointer',
          textAlign: 'center',
          minHeight: '150px'
        }}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input 
          type="file" 
          ref={fileInputRef} 
          onChange={handleFileChange} 
          style={{ display: 'none' }}
          accept="video/*"
        />
        {file ? (
          <p style={{ fontWeight: 500, color: 'var(--color-focus)' }}>Selected: {file.name}</p>
        ) : (
          <>
            <p style={{ marginBottom: 'var(--space-2)' }}>Drag & drop a video file here</p>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' }}>or click to browse</p>
          </>
        )}
      </div>

      <div style={{ marginTop: 'var(--space-3)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          {uploadStatus === 'uploading' && <span style={{ color: 'var(--color-severity-info)', fontSize: 'var(--text-sm)' }}>Uploading...</span>}
          {uploadStatus === 'success' && <span style={{ color: 'var(--color-success)', fontSize: 'var(--text-sm)' }}>Upload complete!</span>}
          {uploadStatus === 'error' && <span style={{ color: 'var(--color-severity-critical)', fontSize: 'var(--text-sm)' }}>{errorMessage}</span>}
        </div>
        <button 
          className="btn" 
          onClick={handleUpload} 
          disabled={!file || uploadStatus === 'uploading'}
        >
          {uploadStatus === 'uploading' ? 'Uploading...' : 'Upload'}
        </button>
      </div>
    </section>
  );
}
