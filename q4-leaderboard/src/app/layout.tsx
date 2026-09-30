import type { Metadata, Viewport } from 'next';
import '@fontsource-variable/inter';
import '@fontsource-variable/plus-jakarta-sans';
import './globals.css';
import { headers } from 'next/headers';
import { getEvent } from '@/lib/data';
import { getCurrentUser } from '@/lib/auth';
import { siteClosedFor, writeBlockedMessage } from '@/lib/maintenance';

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

// While the site is closed for maintenance, admins must still be able to sign in.
const OPEN_WHEN_CLOSED = ['/logowanie', '/reset-hasla', '/nowe-haslo'];

async function maintenanceState(): Promise<{ closed: boolean; readonlyMessage: string | null; message: string }> {
  try {
    const [event, user, h] = await Promise.all([getEvent(), getCurrentUser(), headers()]);
    const path = h.get('x-pathname') ?? '/';
    return {
      closed: siteClosedFor(event, user) && !OPEN_WHEN_CLOSED.some((p) => path.startsWith(p)),
      readonlyMessage: event.maintenanceMode === 'readonly' ? writeBlockedMessage(event, user) : null,
      message: event.maintenanceMessage,
    };
  } catch {
    return { closed: false, readonlyMessage: null, message: '' }; // pages report database problems themselves
  }
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const m = await maintenanceState();
  return (
    <html lang="pl">
      <body className="min-h-dvh font-sans antialiased">
        {m.readonlyMessage && (
          <div role="status" className="bg-accent px-4 py-2 text-center text-sm font-semibold text-accent-fg">
            {m.readonlyMessage}
          </div>
        )}
        {m.closed ? <MaintenancePage message={m.message} /> : children}
      </body>
    </html>
  );
}

function MaintenancePage({ message }: { message: string }) {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center px-6 text-center">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/brand/next-level-logo.png" alt="Next Level" width={130} height={80} className="h-20 w-auto rounded-2xl bg-header p-3" />
      <h1 className="mt-6 text-2xl font-extrabold">Przerwa techniczna</h1>
      <p className="mt-2 text-white/80">{message || 'Aktualizujemy ranking. Wróć za chwilę — Twoje wyniki są bezpieczne.'}</p>
    </main>
  );
}
