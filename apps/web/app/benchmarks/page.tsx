import { BenchmarkRunner } from '@/components/BenchmarkRunner';
import { SiteNav } from '@/components/SiteNav';

export default function BenchmarksPage() {
  return (
    <main className="page-shell compact-shell">
      <SiteNav ariaLabel="Benchmark navigation" current="benchmarks" compact />

      <section className="minimal-hero benchmark-hero" aria-labelledby="benchmark-title">
        <p className="eyebrow">Full demo</p>
        <h1 id="benchmark-title">Run the real benchmark workflow.</h1>
        <p>
          This is the product screen: choose a domain scenario, simulate a run, inspect task completion, action
          trace, policy, and final-state scores, then export the evidence.
        </p>
        <div className="demo-pill-row" aria-label="Demo highlights">
          <span>Scenario simulation</span>
          <span>Evidence inspection</span>
          <span>Exportable reports</span>
        </div>
      </section>

      <BenchmarkRunner />
    </main>
  );
}
