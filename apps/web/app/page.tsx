import Link from 'next/link';
import { SiteNav } from '@/components/SiteNav';

const domains = [
  {
    name: 'Call center voice AI',
    detail: 'Appointments, cancellations, transfers, interruptions, escalation.',
  },
  {
    name: 'Telehealth intake',
    detail: 'Patient routing, privacy boundaries, medication and emergency handling.',
  },
  {
    name: 'Online teaching',
    detail: 'Adaptive tutoring, quiz flow, confusion handling, grading boundaries.',
  },
  {
    name: 'Fintech support',
    detail: 'Identity checks, disputes, card freezes, fraud escalation, compliance.',
  },
];

const surfaces = [
  {
    title: 'Conversations',
    copy: 'Score transcripts, chats, and vCon records against scenario expectations.',
  },
  {
    title: 'Voice AI',
    copy: 'Evaluate real-time calls, interruptions, escalation, and voice-specific behavior.',
  },
  {
    title: 'Group calls',
    copy: 'Track speakers, decisions, commitments, and follow-up actions across multi-party sessions.',
  },
  {
    title: 'E2E actions',
    copy: 'Verify tools, policy constraints, and final system state in one report.',
  },
];

const workflow = [
  {
    label: 'Define',
    title: 'Write scenarios that match real jobs',
    copy: 'Capture persona, task goal, policy constraints, required actions, forbidden actions, and expected final state.',
  },
  {
    label: 'Run',
    title: 'Simulate agent behavior across channels',
    copy: 'Start with text and tool traces, then graduate the same benchmarks to voice, WebRTC, and phone workflows.',
  },
  {
    label: 'Score',
    title: 'Measure outcomes, not vibes',
    copy: 'Grade task completion, action correctness, policy compliance, final state, and evidence artifacts.',
  },
];

const signals = [
  'Task completion',
  'Tool/action correctness',
  'Policy boundaries',
  'Final-state assertions',
  'Voice and WebRTC readiness',
  'Evidence artifacts',
];

const proofRows = [
  ['Scenario', 'Angry caller needs appointment reschedule'],
  ['Evidence', 'Transcript, action trace, final state'],
  ['Scores', 'Task, policy, tool, outcome'],
  ['Output', 'Pass/fail report with suggested fixes'],
];

export default function HomePage() {
  return (
    <main className="saas-shell">
      <SiteNav current="home">
        <>
          <a href="#product">Product</a>
          <a href="#coverage">Coverage</a>
          <a href="#benchmarks">Benchmarks</a>
        </>
      </SiteNav>

      <section className="saas-hero" aria-labelledby="hero-title">
        <div className="saas-hero-copy">
          <p className="eyebrow">Agentic AI evaluation platform</p>
          <h1 id="hero-title">Prove your AI agent can actually do the job.</h1>
          <p>
            Evaluate conversations, voice AI, group calls, tool execution, and final task outcomes in one
            regression platform before agents reach production.
          </p>
          <div className="hero-cta">
            <Link className="primary-link" href="/benchmarks">Open full demo</Link>
            <Link className="secondary-link" href="/pricing">See pricing</Link>
          </div>
        </div>

        <aside className="score-panel" aria-label="Benchmark report preview">
          <div className="score-panel-header">
            <span>Benchmark report</span>
            <strong>91</strong>
          </div>
          <div className="score-bars">
            <ScoreRow label="Task completion" value="94%" />
            <ScoreRow label="Policy compliance" value="88%" />
            <ScoreRow label="Tool correctness" value="91%" />
            <ScoreRow label="Final state" value="90%" />
          </div>
        </aside>
      </section>

      <section className="section-band" id="product" aria-labelledby="product-title">
        <div className="section-heading">
          <p className="eyebrow">Product</p>
          <h2 id="product-title">A regression suite for agentic behavior.</h2>
          <p>
            Most eval tools stop at conversation quality. This tests whether the agent understood the user,
            handled the channel correctly, executed the right actions, respected constraints, and left systems
            in the correct state.
          </p>
        </div>
        <div className="signal-grid">
          {signals.map((signal) => (
            <div className="signal-item" key={signal}>{signal}</div>
          ))}
        </div>
      </section>

      <section className="coverage-section" id="coverage" aria-labelledby="coverage-title">
        <div className="section-heading">
          <p className="eyebrow">Coverage</p>
          <h2 id="coverage-title">One evaluation layer across every agent surface.</h2>
        </div>
        <div className="surface-grid">
          {surfaces.map((surface) => (
            <article className="surface-card" key={surface.title}>
              <h3>{surface.title}</h3>
              <p>{surface.copy}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="proof-section" aria-labelledby="proof-title">
        <div className="section-heading">
          <p className="eyebrow">Workspace</p>
          <h2 id="proof-title">The live demo stays focused on the real workflow.</h2>
          <p>
            The full demo has its own screen so buyers can inspect a real benchmark run without competing against
            the homepage story. The homepage stays on positioning, and the demo stays on evidence.
          </p>
        </div>
        <div className="proof-table" aria-label="Benchmark runner workflow preview">
          {proofRows.map(([label, value]) => (
            <div className="proof-row" key={label}>
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
      </section>

      <section className="route-section" aria-labelledby="route-title">
        <div className="section-heading">
          <p className="eyebrow">Screens</p>
          <h2 id="route-title">Three screens, three jobs.</h2>
          <p>
            Split the experience by intent: explain the product on the homepage, discuss rollout economics on the
            pricing page, and keep the full benchmark runner on its own screen for hands-on evaluation.
          </p>
        </div>
        <div className="route-grid">
          <article className="route-card">
            <span>Homepage</span>
            <h3>Why this category matters</h3>
            <p>Position the product, show coverage, and explain what gets measured before an agent ships.</p>
            <Link className="secondary-link" href="#product">Read the story</Link>
          </article>
          <article className="route-card route-card-featured">
            <span>Full demo</span>
            <h3>Run a real scenario benchmark</h3>
            <p>Open the runner to simulate a suite, inspect evidence, and export structured eval reports.</p>
            <Link className="primary-link" href="/benchmarks">Launch the demo</Link>
          </article>
          <article className="route-card">
            <span>Pricing</span>
            <h3>Qualify the first paid rollout</h3>
            <p>Explain pilot shape, packaging, and what teams buy once they need repeated evidence, not screenshots.</p>
            <Link className="secondary-link" href="/pricing">Open pricing</Link>
          </article>
        </div>
      </section>

      <section className="workflow-section" aria-labelledby="workflow-title">
        <div className="section-heading">
          <p className="eyebrow">Workflow</p>
          <h2 id="workflow-title">Text-first benchmarks that graduate to voice.</h2>
        </div>
        <div className="workflow-grid">
          {workflow.map((item) => (
            <article className="workflow-card" key={item.label}>
              <span>{item.label}</span>
              <h3>{item.title}</h3>
              <p>{item.copy}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section-band" id="benchmarks" aria-labelledby="benchmarks-title">
        <div className="section-heading">
          <p className="eyebrow">Benchmark families</p>
          <h2 id="benchmarks-title">Designed for consequential agent workflows.</h2>
        </div>
        <div className="domain-strip">
          {domains.map((domain) => (
            <article key={domain.name}>
              <h3>{domain.name}</h3>
              <p>{domain.detail}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="cta-band">
        <div>
          <p className="eyebrow">MVP</p>
          <h2>Start with the right screen.</h2>
          <p>Use the full demo for proof, and the pricing screen for the commercial conversation.</p>
        </div>
        <div className="cta-actions">
          <Link className="secondary-link" href="/pricing">View pricing</Link>
          <Link className="primary-link" href="/benchmarks">Launch demo</Link>
        </div>
      </section>
    </main>
  );
}

function ScoreRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="score-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
