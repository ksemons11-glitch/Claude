import Link from 'next/link';
import { Header } from '@/components/Header';
import { requireAdmin } from '@/lib/auth';
import { query } from '@/lib/db';

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  await requireAdmin();
  const [counts] = await query<{ pending: number; corrections: number; deletions: number }>(
    `SELECT
       (SELECT COUNT(*) FROM users WHERE status = 'pending') AS pending,
       (SELECT COUNT(*) FROM correction_requests WHERE status = 'open') AS corrections,
       (SELECT COUNT(*) FROM users WHERE deletion_requested_at IS NOT NULL AND status <> 'deleted') AS deletions`,
  );
  const badge = (n: number) =>
    Number(n) > 0 ? <span className="ml-1.5 rounded-full bg-accent px-1.5 text-xs font-bold text-bg">{Number(n)}</span> : null;
  const links = [
    { href: '/admin', label: 'Oczekujące', extra: badge(counts.pending) },
    { href: '/admin/uzytkownicy', label: 'Uczestnicy', extra: badge(counts.deletions) },
    { href: '/admin/korekty', label: 'Korekty', extra: badge(counts.corrections) },
    { href: '/admin/tygodnie', label: 'Tygodnie', extra: null },
    { href: '/admin/dziennik', label: 'Dziennik zmian', extra: null },
    { href: '/admin/ustawienia', label: 'Ustawienia', extra: null },
  ];
  return (
    <>
      <Header />
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
        {children}
      </div>
    </>
  );
}
