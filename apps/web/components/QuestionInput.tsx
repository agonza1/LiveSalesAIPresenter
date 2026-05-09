'use client';

import { FormEvent, useState } from 'react';

interface QuestionInputProps {
  busy: boolean;
  voiceActive?: boolean;
  onSubmit: (question: string) => Promise<void>;
  onSimulateVoice?: (question: string) => Promise<void>;
  onStartVoice?: () => Promise<void>;
  onStopVoice?: () => Promise<void>;
}

export function QuestionInput({ busy, voiceActive, onSubmit, onSimulateVoice, onStartVoice, onStopVoice }: QuestionInputProps) {
  const [question, setQuestion] = useState('');

  async function submitQuestion(mode: 'ask' | 'voice') {
    const trimmed = question.trim();
    if (!trimmed) return;
    if (mode === 'voice' && onSimulateVoice) {
      await onSimulateVoice(trimmed);
    } else {
      await onSubmit(trimmed);
    }
    setQuestion('');
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitQuestion('ask');
  }

  return (
    <form onSubmit={handleSubmit} style={{ marginTop: 20 }}>
      <label style={{ display: 'block', marginBottom: 8, color: 'var(--muted)' }}>Ask a question</label>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <input
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="How do you compare to competitors?"
          style={{
            flex: 1,
            minHeight: 52,
            borderRadius: 14,
            border: '1px solid rgba(15,23,42,0.12)',
            background: '#ffffff',
            color: 'var(--text)',
            padding: '0 16px',
            minWidth: 260,
          }}
        />
        <button
          type="submit"
          disabled={busy}
          style={{
            border: 'none',
            borderRadius: 14,
            minWidth: 120,
            background: 'linear-gradient(135deg, #2563eb, #0ea5e9)',
            color: '#ffffff',
            fontWeight: 700,
            minHeight: 52,
          }}
        >
          {busy ? 'Working…' : 'Ask'}
        </button>
        <button
          type="button"
          disabled={busy || !onSimulateVoice}
          onClick={() => void submitQuestion('voice')}
          style={{
            borderRadius: 14,
            minWidth: 180,
            minHeight: 52,
            border: '1px solid rgba(37,99,235,0.25)',
            background: '#eff6ff',
            color: '#1d4ed8',
            fontWeight: 700,
          }}
        >
          Simulate voice question
        </button>
        <button
          type="button"
          disabled={busy || voiceActive || !onStartVoice}
          onClick={() => void onStartVoice?.()}
          style={{
            borderRadius: 14,
            minWidth: 180,
            minHeight: 52,
            border: '1px solid rgba(16,185,129,0.3)',
            background: '#ecfdf5',
            color: '#047857',
            fontWeight: 700,
          }}
        >
          {voiceActive ? 'Voice live' : 'Start live voice'}
        </button>
        <button
          type="button"
          disabled={busy || !voiceActive || !onStopVoice}
          onClick={() => void onStopVoice?.()}
          style={{
            borderRadius: 14,
            minWidth: 140,
            minHeight: 52,
            border: '1px solid rgba(239,68,68,0.25)',
            background: '#fef2f2',
            color: '#b91c1c',
            fontWeight: 700,
          }}
        >
          Stop voice
        </button>
      </div>
    </form>
  );
}
