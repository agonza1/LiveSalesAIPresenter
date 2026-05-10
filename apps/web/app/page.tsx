import { DeckLaunchpad } from '@/components/DeckLaunchpad';

export default function HomePage() {
  return (
    <main className="page-shell" style={{ display: 'grid', gap: 24 }}>
      <div className="card" style={{ maxWidth: 1100, padding: 32 }}>
        <p style={{ color: 'var(--accent)', marginTop: 0 }}>Live Sales AI Presenter</p>
        <h1 style={{ marginTop: 0, fontSize: 46 }}>Avatar-led AI sales presentations for PDF decks.</h1>
        <p style={{ color: 'var(--muted)', lineHeight: 1.7, maxWidth: 800 }}>
          This MVP pairs a Next.js presentation surface with a FastAPI backend that preprocesses PDFs into slides,
          creates public presentation sessions, and supports deterministic start/pause/resume/ask flows with a live voice path and Pipecat-powered HeyGen video avatar.
        </p>
        <p style={{ color: 'var(--text)', marginBottom: 0 }}>
          Local demo loop: use the built-in sample deck or upload a PDF, create a session, open the generated link, then run the presentation controls from that tab.
        </p>
      </div>

      <DeckLaunchpad />
    </main>
  );
}
