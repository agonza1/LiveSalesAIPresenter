import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Live Sales AI Presenter',
  description: 'Avatar-led AI sales deck presentations with slide-aware Q&A.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
