'use client';

import { useEffect, useRef, useState } from 'react';
import { Room, RoomEvent, Track } from 'livekit-client';
import { startHeyGenAvatarSession } from '@/lib/api';

interface HeyGenAvatarPanelProps {
  sessionId: string;
  talkTrack: string;
  speaking: boolean;
}

type AvatarStatus = 'idle' | 'starting' | 'ready' | 'speaking' | 'error';

export function HeyGenAvatarPanel({ sessionId, talkTrack, speaking }: HeyGenAvatarPanelProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const roomRef = useRef<Room | null>(null);
  const [status, setStatus] = useState<AvatarStatus>('idle');
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    async function startAvatarTransport() {
      setStatus('starting');
      setError('');

      try {
        const response = await startHeyGenAvatarSession(sessionId);
        const join = response.heygen;
        if (!join?.livekit_url || !join?.access_token) {
          throw new Error(response.nextStep || 'Pipecat HeyGen transport is still starting.');
        }
        if (cancelled) return;

        const room = new Room();
        roomRef.current = room;

        room.on(RoomEvent.TrackSubscribed, (track) => {
          if (track.kind !== Track.Kind.Video || !videoRef.current) return;
          track.attach(videoRef.current);
          void videoRef.current.play().catch(() => undefined);
          setStatus('ready');
        });
        room.on(RoomEvent.Disconnected, () => setStatus('idle'));

        await room.connect(join.livekit_url, join.access_token);
        if (!cancelled) setStatus('ready');
      } catch (err) {
        setStatus('error');
        setError(err instanceof Error ? err.message : 'Pipecat HeyGen avatar failed to start');
      }
    }

    void startAvatarTransport();

    return () => {
      cancelled = true;
      const room = roomRef.current;
      roomRef.current = null;
      room?.disconnect();
    };
  }, [sessionId]);

  useEffect(() => {
    if (status === 'ready' && speaking) setStatus('speaking');
    if (status === 'speaking' && !speaking) setStatus('ready');
  }, [speaking, status]);

  const statusLabel = status.charAt(0).toUpperCase() + status.slice(1);

  return (
    <div className="card" style={{ padding: 20 }}>
      <h3 style={{ marginTop: 0 }}>Video avatar presenter</h3>
      <div
        style={{
          aspectRatio: '4 / 5',
          borderRadius: 18,
          background: 'linear-gradient(180deg, #020617, #0f172a)',
          border: '1px solid rgba(15,23,42,0.08)',
          display: 'grid',
          placeItems: 'center',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <video
          ref={videoRef}
          autoPlay
          playsInline
          style={{ width: '100%', height: '100%', objectFit: 'cover', background: '#020617' }}
        />
        {status !== 'ready' && status !== 'speaking' ? (
          <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', textAlign: 'center', padding: 24, color: '#e2e8f0' }}>
            <div>
              <strong>{status === 'starting' ? 'Starting Pipecat HeyGen avatar…' : 'Pipecat HeyGen avatar'}</strong>
              <p style={{ margin: '8px 0 0', color: '#94a3b8', lineHeight: 1.5 }}>
                {error || 'Waiting for the LiveKit avatar video.'}
              </p>
            </div>
          </div>
        ) : null}
        <div
          style={{
            position: 'absolute',
            top: 16,
            right: 16,
            padding: '6px 10px',
            borderRadius: 999,
            background: status === 'speaking' ? 'rgba(37,99,235,0.84)' : 'rgba(15,23,42,0.68)',
            color: '#ffffff',
            fontSize: 12,
            fontWeight: 700,
          }}
        >
          {statusLabel}
        </div>
      </div>
      <div style={{ marginTop: 14 }}>
        <p style={{ marginBottom: 6, color: 'var(--muted)' }}>Current talk track</p>
        <p style={{ margin: 0, lineHeight: 1.5 }}>{talkTrack}</p>
      </div>
    </div>
  );
}
