import Link from 'next/link';
import type { Route } from 'next';
import type { ReactNode } from 'react';

type RouteKey = 'home' | 'pricing' | 'benchmarks';

const routeLinks: Array<{ href: Route; label: string; key: RouteKey }> = [
  { href: '/', label: 'Homepage', key: 'home' },
  { href: '/pricing', label: 'Pricing', key: 'pricing' },
  { href: '/benchmarks', label: 'Full demo', key: 'benchmarks' },
];

interface SiteNavProps {
  ariaLabel?: string;
  current?: RouteKey;
  children?: ReactNode;
  compact?: boolean;
}

export function SiteNav({ ariaLabel = 'Primary', current, children, compact = false }: SiteNavProps) {
  return (
    <nav className={`top-nav${compact ? ' compact-nav' : ''}`} aria-label={ariaLabel}>
      <Link className="brand" href="/">AgentBench</Link>
      <div className="top-nav-links">
        {children}
        {routeLinks.map((link) => (
          <Link
            key={link.key}
            className={link.key === current ? 'nav-active' : undefined}
            aria-current={link.key === current ? 'page' : undefined}
            href={link.href}
          >
            {link.label}
          </Link>
        ))}
      </div>
    </nav>
  );
}
