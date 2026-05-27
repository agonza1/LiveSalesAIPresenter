import Link from 'next/link';
import { SiteNav } from '@/components/SiteNav';

const plans = [
  {
    name: 'Prototype',
    price: '$1.5k',
    cadence: '/ month',
    summary: 'For one team proving the first benchmark loop.',
    detail: 'Best when the goal is replacing manual scenario calling with structured text-first evals.',
    features: [
      '1 benchmark family',
      'Up to 25 core scenarios',
      'Shared evaluation workspace',
      'JSON, CSV, and Markdown exports',
    ],
  },
  {
    name: 'Team',
    price: '$4k',
    cadence: '/ month',
    summary: 'For product and QA teams running benchmark regressions every release.',
    detail: 'Adds parallel suites, baseline tracking, and rollout discipline around repeated agent changes.',
    features: [
      'Up to 4 benchmark families',
      'Regression history and run comparisons',
      'Prompt, model, and agent version context',
      'Priority support for eval design',
    ],
    featured: true,
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    cadence: '',
    summary: 'For voice programs with strict evidence, audit, and integration requirements.',
    detail: 'For multi-team deployments that need tailored policy assertions, exports, and rollout controls.',
    features: [
      'Custom scenario volume',
      'Voice and WebRTC rollout planning',
      'Private deployment options',
      'Security and compliance review support',
    ],
  },
];

const buyingSignals = [
  'You are rerunning the same voice or chat scenarios after every prompt, model, or tool change.',
  'Your team needs evidence artifacts that can survive a product review, release review, or customer pilot.',
  'Conversation quality alone is no longer enough because action correctness and final state now matter.',
];

const included = [
  ['Benchmark design', 'Scenario structure, constraints, rubrics, and evidence fields grounded in the actual job.'],
  ['Regression workflow', 'Saved runs, score deltas, failure categories, and repeatable exports instead of ad hoc screenshots.'],
  ['Voice readiness', 'A text-first path that graduates toward live voice and WebRTC once the benchmark logic is stable.'],
];

export default function PricingPage() {
  return (
    <main className="saas-shell">
      <SiteNav ariaLabel="Pricing navigation" current="pricing" />

      <section className="saas-hero pricing-hero" aria-labelledby="pricing-title">
        <div className="saas-hero-copy">
          <p className="eyebrow">Pricing</p>
          <h1 id="pricing-title">Price the eval loop, not just another dashboard.</h1>
          <p>
            Teams buy this when repeated agent changes need disciplined benchmark runs, evidence exports, and a
            clear path from text scenarios to voice readiness.
          </p>
          <div className="hero-cta">
            <Link className="primary-link" href="/benchmarks">Open full demo</Link>
            <Link className="secondary-link" href="/">Back to homepage</Link>
          </div>
        </div>

        <aside className="score-panel pricing-panel" aria-label="Ideal customer signals">
          <div className="score-panel-header">
            <span>Best fit</span>
            <strong>Now</strong>
          </div>
          <div className="score-bars">
            {buyingSignals.map((signal) => (
              <div className="score-row score-row-stack" key={signal}>
                <strong>{signal}</strong>
              </div>
            ))}
          </div>
        </aside>
      </section>

      <section className="section-band" aria-labelledby="plans-title">
        <div className="section-heading">
          <p className="eyebrow">Plans</p>
          <h2 id="plans-title">Start with a pilot, then scale the benchmark program.</h2>
          <p>
            The packaging is meant to match how teams adopt evaluation: first prove the regression loop, then expand
            scenario coverage and operational rigor.
          </p>
        </div>
        <div className="plan-grid">
          {plans.map((plan) => (
            <article className={`plan-card${plan.featured ? ' plan-card-featured' : ''}`} key={plan.name}>
              <p className="plan-tier">{plan.name}</p>
              <h3>
                {plan.price}
                <span>{plan.cadence}</span>
              </h3>
              <p className="plan-summary">{plan.summary}</p>
              <p className="plan-detail">{plan.detail}</p>
              <div className="plan-divider" />
              <ul className="plan-list" aria-label={`${plan.name} plan features`}>
                {plan.features.map((feature) => (
                  <li key={feature}>{feature}</li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </section>

      <section className="section-band" aria-labelledby="included-title">
        <div className="section-heading">
          <p className="eyebrow">Included</p>
          <h2 id="included-title">What the engagement actually buys.</h2>
        </div>
        <div className="included-grid">
          {included.map(([title, detail]) => (
            <article className="included-card" key={title}>
              <h3>{title}</h3>
              <p>{detail}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="cta-band">
        <div>
          <p className="eyebrow">Next step</p>
          <h2>Use the demo to qualify the product, then use pricing to qualify the deal.</h2>
          <p>The pages now do separate jobs on purpose.</p>
        </div>
        <div className="cta-actions">
          <Link className="secondary-link" href="/">Homepage</Link>
          <Link className="primary-link" href="/benchmarks">Launch demo</Link>
        </div>
      </section>
    </main>
  );
}
