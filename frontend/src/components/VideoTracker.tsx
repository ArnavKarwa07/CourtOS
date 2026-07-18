import React, { useState, useEffect } from 'react';

interface Video {
  id: string;
  filename: string;
  status: 'processing' | 'ready' | 'error';
  url?: string;
  uploaded_at: string;
}

export default function VideoTracker() {
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchVideos = async () => {
    try {
      const res = await fetch('/api/v1/videos');
      if (!res.ok) throw new Error('Failed to fetch videos');
      const data = await res.json();
      setVideos(data.videos || data || []);
      setError('');
    } catch (err: any) {
      setError('Could not load videos.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVideos();
    const intervalId = setInterval(fetchVideos, 2000);
    return () => clearInterval(intervalId);
  }, []);

  return (
    <section className="panel" style={{ gridArea: 'tracker', maxHeight: '360px', overflow: 'hidden' }}>
      <div className="panel-header">
        <h2 className="panel-title">Video Library</h2>
        <span className="badge badge-info">{videos.length} Total</span>
      </div>
      
      <div style={{ flexGrow: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
        {loading && videos.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 'var(--space-4) 0', color: 'var(--color-text-secondary)' }}>
            Loading videos...
          </div>
        ) : error && videos.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 'var(--space-4) 0', color: 'var(--color-severity-critical)' }}>
            {error}
          </div>
        ) : videos.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 'var(--space-4) 0', color: 'var(--color-text-secondary)' }}>
            No videos uploaded yet.
          </div>
        ) : (
          <ul className="scroll-list" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
            {videos.map(video => (
              <li 
                key={video.id} 
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: 'var(--space-2)',
                  backgroundColor: 'var(--color-surface-elevated)',
                  borderRadius: 'var(--radius-sm)',
                  borderLeft: `4px solid ${
                    video.status === 'ready' ? 'var(--color-success)' :
                    video.status === 'error' ? 'var(--color-severity-critical)' : 'var(--color-focus)'
                  }`
                }}
              >
                <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                  <span style={{ fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {video.filename}
                  </span>
                  <span style={{ fontSize: '10px', color: 'var(--color-text-secondary)' }}>
                    {new Date(video.uploaded_at).toLocaleString()}
                  </span>
                </div>
                <div style={{ marginLeft: 'var(--space-2)' }}>
                  <span className={`badge ${
                    video.status === 'ready' ? 'badge-info' : 
                    video.status === 'error' ? 'badge-critical' : 'badge-warning'
                  }`}>
                    {video.status}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
