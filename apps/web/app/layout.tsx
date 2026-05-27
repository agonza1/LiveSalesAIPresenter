import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'AgentBench',
  description:
    'Homepage, pricing, and a full benchmark demo for proving whether AI agents can actually do the job.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
