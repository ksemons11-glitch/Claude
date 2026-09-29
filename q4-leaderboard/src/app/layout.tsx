import type { Metadata, Viewport } from 'next';
import './globals.css';
import { getEvent } from '@/lib/data';

export const dynamic = 'force-dynamic';

export async function generateMetadata(): Promise<Metadata> {
  const event = await getEvent();
  return {
    title: event.name,
    description: 'Ranking przychodów uczestników w Q4.',
    robots: { index: false, follow: false },
  };
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#0b0f1a',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pl">
      <body className="min-h-dvh font-sans antialiased">{children}</body>
    </html>
  );
}
