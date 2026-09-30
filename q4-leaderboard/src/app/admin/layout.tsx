import Link from 'next/link';
import { Header } from '@/components/Header';
import { requireAdmin } from '@/lib/auth';
import { after } from 'next/server';
import { query } from '@/lib/db';
import { getEvent } from '@/lib/data';
import { ensureDailyBackup } from '@/lib/backup';

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  await requireAdmin();
  after(() => ensureDailyBackup().catch((err) => console.error('[backup] daily backup failed', err)));
  const event = await getEvent();
  const [counts] = await query<{ pending: number; corrections: number; deletions: number }>(
    `SELECT
       (SELECT COUNT(*) FROM users WHERE status = 'pending') AS pending,
       (SELECT COUNT(*) FROM correction_requests WHERE status = 'open') AS corrections,
       (SELECT COUNT(*) FROM users WHERE deletion_requested_at IS NOT NULL AND status <> 'deleted') AS deletions`,
  );
  const badge = (n: number) =>
    Number(n) > 0 ? <span className="ml-1.5 rounded-full bg-accent px-1.5 text-xs font-bold text-accent-fg">{Number(n)}</span> : null;
  const links = [
    { href: '/admin', label: 'Oczekujące', extra: badge(counts.pending) },
    { href: '/admin/uzytkownicy', label: 'Uczestnicy', extra: badge(counts.deletions) },
    { href: '/admin/korekty', label: 'Korekty', extra: badge(counts.corrections) },
    { href: '/admin/tygodnie', label: 'Tygodnie', extra: null },
    { href: '/admin/dziennik', label: 'Dziennik zmian', extra: null },
    { href: '/admin/ustawienia', label: 'Ustawienia', extra: null },
    { href: '/admin/kopie', label: 'Kopie i serwis', extra: null },
  ];
  return (
    <>
      <Header wide />
      <div className="mx-auto max-w-5xl px-4 pb-16 pt-4">
        <nav className="-mx-4 mb-5 overflow-x-auto px-4">
          <div className="flex w-max gap-1.5">
            {links.map((l) => (
              <Link key={l.href} href={l.href} className="btn-sm whitespace-nowrap border border-line bg-card hover:bg-white/5">
                {l.label}
                {l.extra}
              </Link>
            ))}
            <a href="/api/admin/export?type=users" className="btn-sm whitespace-nowrap border border-line bg-card hover:bg-white/5">CSV: uczestnicy</a>
            <a href="/api/admin/export?type=entries" className="btn-sm whitespace-nowrap border border-line bg-card hover:bg-white/5">CSV: wyniki</a>
          </div>
        </nav>
        {event.maintenanceMode !== 'off' && (
          <p className="alert-error mb-5">
            <b>{event.maintenanceMode === 'closed' ? 'Przerwa techniczna włączona' : 'Tryb „tylko odczyt” włączony'}</b> — uczestnicy{' '}
            {event.maintenanceMode === 'closed' ? 'nie widzą strony' : 'nie mogą niczego zapisać'}. Wyłączysz go w zakładce{' '}
            <Link href="/admin/kopie" className="underline">Kopie i serwis</Link>.
          </p>
        )}
        {children}
      </div>
    </>
  );
}
