import type { Metadata, Viewport } from 'next';
import '@fontsource-variable/inter';
import '@fontsource-variable/plus-jakarta-sans';
import './globals.css';
import { getEvent } from '@/lib/data';

export const dynamic = 'force-dynamic';

export async function generateMetadata(): Promise<Metadata> {
  // Falls back to a fixed title so the app can also be built without a database connection.
  const name = await getEvent()
    .then((e) => e.name)
    .catch(() => 'Q4 Leaderboard');
  return {
    title: name,
    description: 'Ranking przychodów uczestników w Q4.',
    robots: { index: false, follow: false },
  };
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#050505',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pl">
      <body className="min-h-dvh font-sans antialiased">{children}</body>
    </html>
  );
}
