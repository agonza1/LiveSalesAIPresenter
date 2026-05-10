'use client';

import { useEffect, useRef, useState } from 'react';
import StreamingAvatar, { AvatarQuality, StreamingEvents, TaskMode, TaskType, VoiceEmotion } from '@heygen/streaming-avatar';
import { createHeyGenToken } from '@/lib/api';

interface HeyGenAvatarPanelProps {
  talkTrack: string;
  speaking: boolean;
}

type AvatarStatus = 'idle' | 'starting' | 'ready' | 'speaking' | 'error';

export function HeyGenAvatarPanel({ talkTrack, speaking }: HeyGenAvatarPanelProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const avatarRef = useRef<StreamingAvatar | null>(null);
  const lastSpokenRef = useRef('');
  const startingRef = useRef(false);
  const [status, setStatus] = useState<AvatarStatus>('idle');
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    async function startAvatar() {
      if (startingRef.current || avatarRef.current) return;
      startingRef.current = true;
      setStatus('starting');
      setError('');

      try {
        const token = await createHeyGenToken();
        if (cancelled) return;

        const avatar = new StreamingAvatar({ token: token.token });
        avatarRef.current = avatar;

        avatar.on(StreamingEvents.STREAM_READY, (event) => {
          const maybeStream = (event as { detail?: MediaStream; stream?: MediaStream })?.detail ?? (event as { stream?: MediaStream })?.stream ?? avatar.mediaStream;
          if (videoRef.current && maybeStream) {
            videoRef.current.srcObject = maybeStream;
            void videoRef.current.play().catch(() => undefined);
          }
          setStatus('ready');
        });
        avatar.on(StreamingEvents.AVATAR_START_TALKING, () => setStatus('speaking'));
        avatar.on(StreamingEvents.AVATAR_STOP_TALKING, () => setStatus('ready'));
        avatar.on(StreamingEvents.STREAM_DISCONNECTED, () => setStatus('idle'));

        await avatar.createStartAvatar({
          quality: AvatarQuality.Medium,
          avatarName: token.avatar_id,
          voice: token.voice_id
            ? {
                voiceId: token.voice_id,
                emotion: VoiceEmotion.FRIENDLY,
              }
            : undefined,
          activityIdleTimeout: 600,
        });

        if (videoRef.current && avatar.mediaStream) {
          videoRef.current.srcObject = avatar.mediaStream;
          await videoRef.current.play().catch(() => undefined);
          setStatus('ready');
        }
      } catch (err) {
        setStatus('error');
        setError(err instanceof Error ? err.message : 'HeyGen avatar failed to start');
      } finally {
        startingRef.current = false;
      }
    }

    void startAvatar();

    return () => {
      cancelled = true;
      const avatar = avatarRef.current;
      avatarRef.current = null;
      void avatar?.stopAvatar().catch(() => undefined);
    };
  }, []);

  useEffect(() => {
    const text = talkTrack.trim();
    const avatar = avatarRef.current;
    if (!avatar || !text || text === lastSpokenRef.current || status === 'starting' || status === 'error') return;

    lastSpokenRef.current = text;
    void avatar.speak({ text, task_type: TaskType.REPEAT, taskMode: TaskMode.SYNC }).catch((err) => {
      setError(err instanceof Error ? err.message : 'HeyGen speak failed');
      setStatus('error');
    });
  }, [status, talkTrack]);

  const statusLabel = status === 'ready' && speaking ? 'Ready' : status.charAt(0).toUpperCase() + status.slice(1);

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
          muted={false}
          style={{ width: '100%', height: '100%', objectFit: 'cover', background: '#020617' }}
        />
        {status !== 'ready' && status !== 'speaking' ? (
          <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', textAlign: 'center', padding: 24, color: '#e2e8f0' }}>
            <div>
              <strong>{status === 'starting' ? 'Starting HeyGen avatar…' : 'HeyGen avatar'}</strong>
              <p style={{ margin: '8px 0 0', color: '#94a3b8', lineHeight: 1.5 }}>
                {error || 'Waiting for the streaming avatar video.'}
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
